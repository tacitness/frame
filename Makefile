# frame - pure x86_64 NASM X11 display server

SHELL := /bin/bash
.SHELLFLAGS := -eu -o pipefail -c
.DELETE_ON_ERROR:
.DEFAULT_GOAL := all

NASM     ?= nasm
LD       ?= ld
NFLAGS   ?= -f elf64 -Werror -Wno-unknown-warning
LFLAGS   ?= -z noexecstack -z separate-code -z relro -z now --build-id=sha1 --fatal-warnings
PYTHON   ?= python3

PREFIX   ?= /usr/local
BINDIR   ?= $(PREFIX)/bin
VERSION  ?= $(strip $(shell sed -n '1p' VERSION))
DIST_DIR ?= dist

SCRIPTS := $(shell find scripts .githooks -type f -name '*.sh' -o -type f -path '.githooks/*' 2>/dev/null | sort)
YAML_FILES := $(shell find .github -type f \( -name '*.yml' -o -name '*.yaml' \) -print 2>/dev/null | sort)

.PHONY: all clean install uninstall help debug bench-protocol \
	format-check lint lint-asm lint-shell lint-yaml lint-actions \
	test test-unit test-static test-integration test-protocol test-regression test-fuzz test-reproducible \
	pre-commit quality ci-ro ci-local ci-self-hosted \
	security security-online secrets git-secrets-staged git-secrets-tree git-secrets-history runner-safety \
	sonar-report sonar \
	dist package sbom image image-archive release-artifacts \
	install-hooks hooks-check github-bootstrap github-issues version release-version-check bump-patch bump-minor bump-major

all: frame

frame: frame.o
	$(LD) $(LFLAGS) $< -o $@

frame.o: frame.asm
	$(NASM) $(NFLAGS) $< -o $@

debug: NFLAGS += -g -F dwarf
debug: clean frame

format-check: ## Check text hygiene and whitespace without rewriting source
	$(PYTHON) scripts/check-text.py
	git diff --check
	git diff --cached --check

lint-asm: ## Assemble with fatal warnings and run assembly policy checks
	scripts/lint-asm.sh frame.asm

lint-shell: ## Check every maintained shell script and hook
	bash -n $(SCRIPTS)
	shellcheck $(SCRIPTS)

lint-yaml: ## Validate YAML style, including issue forms and workflows
	yamllint -c .yamllint.yml $(YAML_FILES)

lint-actions: ## Statically validate GitHub Actions semantics
	actionlint

lint: lint-asm lint-shell lint-yaml lint-actions

test-elf test-static: frame ## Verify the linked ELF security and dependency contract
	scripts/check-elf.sh ./frame

test-unit: ## Exercise pure protocol encoding and parsing helpers
	$(PYTHON) -m unittest discover -s tests/unit -p 'test_*.py' -v

test-integration test-protocol: frame ## Exercise a live isolated headless X11 socket
	$(PYTHON) tests/protocol_smoke.py ./frame

test-regression: frame ## Preserve behavior for previously identified server defects
	$(PYTHON) -m unittest discover -s tests/regression -p 'test_*.py' -v

test-fuzz: frame ## Replay bounded malformed-input seeds without hardware access
	$(PYTHON) -m unittest discover -s tests/fuzz -p 'test_*.py' -v

test-reproducible: ## Build twice in clean temporary directories and compare bytes
	scripts/check-reproducible.sh

test: test-unit test-static test-integration test-regression test-fuzz

pre-commit: git-secrets-tree format-check lint test ## Fast local commit gate

quality: pre-commit test-reproducible ## Canonical repository quality gate

ci-ro: quality git-secrets-history ## Read-only CI parity gate; never touches DRM or evdev

git-secrets-staged: ## Scan the staged index with versioned AWS credential rules
	scripts/git-secrets-scan.sh staged

git-secrets-tree: ## Scan tracked and untracked files with git-secrets
	scripts/git-secrets-scan.sh tree

git-secrets-history: ## Scan every reachable revision with git-secrets
	scripts/git-secrets-scan.sh history

secrets: git-secrets-tree git-secrets-history ## Scan history and the working tree with both engines
	gitleaks detect --source . --redact --no-banner
	gitleaks detect --source . --no-git --redact --no-banner

security: secrets test-elf lint-asm ## Offline/local security gate

security-online: security ## Extended scanner gate; may update vulnerability databases
	scripts/security-scan.sh ./frame

sonar-report: ## Generate the versioned NASM/workflow external-issue report
	$(PYTHON) scripts/assembly_policy.py frame.asm --sonar-report out/sonar/frame-policy.json

sonar: sonar-report ## Analyze and wait for the configured SonarQube quality gate
	@test -n "$${SONAR_HOST_URL:-}" || { echo "SONAR_HOST_URL is required" >&2; exit 1; }
	@test -n "$${SONAR_TOKEN:-}" || { echo "SONAR_TOKEN is required" >&2; exit 1; }
	sonar-scanner \
		-Dsonar.host.url="$${SONAR_HOST_URL}" \
		-Dsonar.token="$${SONAR_TOKEN}" \
		-Dsonar.projectVersion="$(VERSION)" \
		-Dsonar.qualitygate.wait=true \
		-Dsonar.qualitygate.timeout=300

runner-safety: ## Fail if a CI runner exposes hardware or elevated identity
	scripts/check-runner-safety.sh

ci-local: quality security ## Full local pre-push parity gate

ci-self-hosted: runner-safety quality security-online ## Trusted ephemeral-runner gate

dist package: frame ## Create a reproducible release tarball and checksums
	scripts/package-release.sh "$(VERSION)" ./frame "$(DIST_DIR)"

sbom: dist ## Generate SPDX and CycloneDX release SBOMs
	scripts/generate-sbom.sh "$(VERSION)" "$(DIST_DIR)"

image: frame ## Build the minimal scratch OCI image locally
	scripts/build-image.sh "$(VERSION)" ./frame

image-archive: frame ## Build and export a scanned Docker-compatible image archive
	scripts/build-image.sh "$(VERSION)" ./frame "$(DIST_DIR)"

release-artifacts: dist sbom image-archive ## Build all package and OCI deliverables

bench-protocol: frame ## Measure headless setup/query latency; informational, never a PR gate
	$(PYTHON) scripts/benchmark-protocol.py ./frame --output out/benchmarks/protocol.json

version: ## Print the tag-derived build version
	@scripts/version.sh current

release-version-check: ## Require RELEASE_TAG to be strict SemVer and point to HEAD
	@scripts/version.sh check "$${RELEASE_TAG:-}"

bump-patch bump-minor bump-major: quality ## Create and push the next annotated SemVer tag
	@kind="$(@:bump-%=%)"; \
	tag="$$(scripts/version.sh next "$$kind")"; \
	git tag -a "$$tag" -m "Release $$tag"; \
	git push origin "$$tag"; \
	echo "Published $$tag"

install: frame
	install -d "$(DESTDIR)$(BINDIR)"
	install -m 0755 frame "$(DESTDIR)$(BINDIR)/frame"

uninstall:
	rm -f -- "$(DESTDIR)$(BINDIR)/frame"

install-hooks: ## Use the versioned hooks in .githooks for this checkout
	git config --local core.hooksPath .githooks
	chmod 0755 .githooks/pre-commit .githooks/commit-msg .githooks/prepare-commit-msg .githooks/pre-push
	@echo "Installed repository hooks from .githooks/"

hooks-check: ## Confirm this checkout uses the versioned hooks
	test "$$(git config --local --get core.hooksPath)" = .githooks
	test -x .githooks/pre-commit
	test -x .githooks/commit-msg
	test -x .githooks/prepare-commit-msg
	test -x .githooks/pre-push

github-issues: ## Reconcile versioned epics, child issues, labels, and milestones
	$(PYTHON) scripts/github-issues-sync.py --apply

github-bootstrap: ## Apply GitHub security, environments, taxonomy, milestones, and issues
	scripts/github-bootstrap.sh --apply

clean:
	rm -f -- frame frame.o
	rm -rf -- "$(DIST_DIR)"

help: ## List primary developer commands
	@echo "frame $(VERSION)"
	@echo "  make quality           format, lint, tests, reproducibility"
	@echo "  make ci-local          quality plus offline security gates"
	@echo "  make ci-self-hosted    runner safety plus online scanners"
	@echo "  make release-artifacts tarball, SBOMs, and OCI archive"
	@echo "  make install-hooks     enable versioned commit/push hooks"
