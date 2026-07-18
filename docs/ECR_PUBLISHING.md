# Private ECR publication

Private ECR is a required release destination, in addition to GHCR and the GitHub Release. Publication is keyless: the protected
GitHub `release` environment exchanges an OIDC token for a short-lived, repository-scoped AWS role. Static AWS access keys are not an
accepted fallback.

## Frame-side contract

The hosted `publish` job loads the already tested/scanned archive after the self-hosted-to-hosted artifact boundary, publishes GHCR,
then publishes the exact same manifest to:

- `494111853453.dkr.ecr.us-west-2.amazonaws.com/frame:vMAJOR.MINOR.PATCH`;
- `494111853453.dkr.ecr.us-west-2.amazonaws.com/frame:sha-<full-commit>`.

The job queries ECR after both pushes and requires their digests to match. ECR deliberately receives no mutable `latest` tag. Consumers
must pin a digest, version, or full-commit tag.

Repository variables:

| Variable | Bootstrap value | Enablement value |
|---|---|---|
| `ECR_ENABLED` | `false` | `true` only after Terraform apply and a publish smoke test |
| `AWS_REGION` | `us-west-2` | unchanged |
| `ECR_REPOSITORY` | `494111853453.dkr.ecr.us-west-2.amazonaws.com/frame` | Terraform output |
| `AWS_ECR_PUBLISH_ROLE_ARN` | unset | Terraform output |

The release preflight fails while `ECR_ENABLED` is not true. The `release` environment requires an approval and accepts only `main`
or `v*` workflow refs. As observed from GitHub's OIDC API on 2026-07-17, the immutable repository subject prefix is
`repo:tacitness@15036814/frame@1304482614`; infrastructure must not broaden this back to `repo:tacitness/frame:*`.

## Dagobah-owned infrastructure contract

Provision this in a small isolated Terraform state such as `terraform/environments/frame-ci`, following the existing
`terraform/environments/tsctl-ci` pattern:

- one private ECR repository named `frame` with immutable tags, scan-on-push, AES-256 encryption, tags, and `prevent_destroy`;
- one lifecycle policy that expires only untagged manifests after a reviewed retention period; version/SHA releases remain retained;
- one GitHub OIDC role whose audience is exactly `sts.amazonaws.com` and whose subject is exactly
  `repo:tacitness@15036814/frame@1304482614:environment:release`;
- an inline policy with global `ecr:GetAuthorizationToken` plus upload, manifest, and read-back actions scoped only to the `frame`
  repository ARN;
- outputs for the role ARN, repository URL, and expected GitHub variable names.

Do not grant repository creation, deletion, lifecycle mutation, cross-repository push, K3s, S3, Secrets Manager, or IAM authority to
the frame role. Do not put AWS credentials in GitHub secrets. [Dagobah issue #429](https://github.com/tacitness/dagobah-infra/issues/429)
is the SDD and human-approval boundary for Terraform plan/apply.

## Rollout

1. Merge frame's workflow and environment bootstrap.
2. Review and implement [Dagobah issue #429](https://github.com/tacitness/dagobah-infra/issues/429) on an issue branch.
3. Run `terraform fmt -check`, `terraform validate`, and a saved plan in the isolated environment; obtain explicit approval before
   apply.
4. Set `AWS_ECR_PUBLISH_ROLE_ARN` and confirm `ECR_REPOSITORY` from Terraform outputs.
5. Keep `ECR_ENABLED=false` for a manual OIDC/ECR smoke check from the protected environment.
6. Set `ECR_ENABLED=true`, publish a new tag, and verify both tags resolve to the attested digest.
7. Deploy only by digest and monitor ECR scanning findings; fix forward with a new patch tag.
