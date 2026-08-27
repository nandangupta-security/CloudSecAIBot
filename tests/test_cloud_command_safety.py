"""
Unit tests for cloud_command_safety.py.

Covers three things for each provider's checker:
  1. Normal read-only usage is allowed.
  2. The specific false positives the old substring blocklist used to
     reject (a read command whose --query/filter text happens to contain
     a blocked word) are now allowed.
  3. The specific false negatives the old blocklist let straight through
     (mutating operations that don't contain any blocklisted word) are
     now blocked.
  4. Edge cases: empty input, malformed quoting, case-insensitivity.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from cloud_command_safety import (
    is_safe_aws_command,
    is_safe_azure_command,
    is_safe_bq_command,
    is_safe_gcloud_command,
    is_safe_gsutil_command,
)


# ─────────────────────────────────────────────────────────────────────────
# AWS
# ─────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("command", [
    "s3 ls",
    "s3api list-buckets",
    "iam list-users",
    "sts get-caller-identity",
    "iam generate-credential-report",
    "ec2 describe-instances",
    "cloudtrail lookup-events",
    "guardduty list-detectors",
    "config describe-config-rules",
    "iam simulate-principal-policy --policy-source-arn x --action-names y",
])
def test_aws_allows_normal_read_commands(command):
    assert is_safe_aws_command(command) is True


def test_aws_allows_query_filter_that_mentions_delete():
    """The exact false positive the old blocklist had: 'delete' appearing
    in a --query filter value, not as the actual operation."""
    command = (
        "cloudformation describe-stack-events "
        "--query \"StackEvents[?ResourceStatus=='DELETE_COMPLETE']\""
    )
    assert is_safe_aws_command(command) is True


@pytest.mark.parametrize("command", [
    "s3 rm s3://bucket/key",
    "s3 sync . s3://bucket",
    "s3 mv s3://a s3://b",
    "s3 mb s3://new-bucket",
    "s3 website s3://bucket --index-document index.html",
    "iam put-user-policy --user-name x --policy-name y --policy-document z",
    "iam attach-role-policy --role-name x --policy-arn y",
    "iam create-access-key --user-name x",
    "iam delete-user --user-name x",
    "ec2 authorize-security-group-ingress --group-id sg-1 --cidr 0.0.0.0/0",
    "ec2 terminate-instances --instance-ids i-123",
    "s3api put-bucket-policy --bucket x --policy y",
])
def test_aws_blocks_mutating_commands_the_old_blocklist_missed(command):
    assert is_safe_aws_command(command) is False


@pytest.mark.parametrize("command", ["", "   ", "s3", "help"])
def test_aws_blocks_incomplete_or_malformed_commands(command):
    assert is_safe_aws_command(command) is False


def test_aws_rejects_unbalanced_quotes_instead_of_raising():
    assert is_safe_aws_command("s3api list-buckets --query 'unterminated") is False


def test_aws_verb_matching_is_case_insensitive():
    assert is_safe_aws_command("IAM LIST-USERS") is True
    assert is_safe_aws_command("IAM PUT-USER-POLICY --user-name x") is False


# ─────────────────────────────────────────────────────────────────────────
# Azure
# ─────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("command", [
    "vm list",
    "network nsg rule list --nsg-name x --resource-group y",
    "role assignment list",
    "ad user list",
    "storage account show --name x",
    "group list",
    "keyvault list",
])
def test_azure_allows_normal_read_commands(command):
    assert is_safe_azure_command(command) is True


@pytest.mark.parametrize("command", [
    "vm delete --name x --resource-group y",
    "role assignment create --assignee x --role Owner",
    "storage account create --name x",
    "group delete --name x",
    "keyvault delete --name x",
    "ad user delete --id x",
])
def test_azure_blocks_mutating_commands(command):
    assert is_safe_azure_command(command) is False


@pytest.mark.parametrize("command", ["", "   "])
def test_azure_blocks_empty_commands(command):
    assert is_safe_azure_command(command) is False


# ─────────────────────────────────────────────────────────────────────────
# gcloud
# ─────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("command", [
    "compute instances list",
    "projects describe my-project",
    "iam service-accounts get-iam-policy sa@x.iam.gserviceaccount.com",
    "compute firewall-rules list",
    "projects list",
])
def test_gcloud_allows_normal_read_commands(command):
    assert is_safe_gcloud_command(command) is True


def test_gcloud_blocks_delete_even_when_a_later_positional_value_looks_like_a_read_verb():
    """Regression test for the specific ordering trap: a resource literally
    named 'get-my-instance' must not make a delete command look safe."""
    assert is_safe_gcloud_command("compute instances delete get-my-instance") is False


@pytest.mark.parametrize("command", [
    "projects add-iam-policy-binding my-project --member=user:x --role=roles/owner",
    "compute firewall-rules create allow-all --allow=tcp",
    "compute instances delete my-instance",
    "iam service-accounts keys create key.json --iam-account=x",
])
def test_gcloud_blocks_mutating_commands(command):
    assert is_safe_gcloud_command(command) is False


# ─────────────────────────────────────────────────────────────────────────
# gsutil
# ─────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("command", [
    "ls gs://bucket",
    "cat gs://bucket/file",
    "du gs://bucket",
    "iam get gs://bucket",
    "acl get gs://bucket",
    "lifecycle get gs://bucket",
])
def test_gsutil_allows_read_commands(command):
    assert is_safe_gsutil_command(command) is True


@pytest.mark.parametrize("command", [
    "rm gs://bucket/key",
    "cp local gs://bucket",
    "iam set policy.json gs://bucket",
    "acl set public-read gs://bucket",
    "lifecycle set config.json gs://bucket",
])
def test_gsutil_blocks_mutating_commands(command):
    assert is_safe_gsutil_command(command) is False


# ─────────────────────────────────────────────────────────────────────────
# bq
# ─────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("command", ["ls", "show mydataset.mytable"])
def test_bq_allows_ls_and_show(command):
    assert is_safe_bq_command(command) is True


def test_bq_blocks_query_even_though_query_is_normally_a_read_verb():
    """bq query runs arbitrary SQL, including DML/DDL — must stay blocked
    even though 'query' is a read verb prefix everywhere else."""
    assert is_safe_bq_command("query --use_legacy_sql=false 'DELETE FROM t WHERE true'") is False
    assert is_safe_bq_command("query 'SELECT * FROM t'") is False


@pytest.mark.parametrize("command", ["rm -t mydataset.mytable", "mk mydataset", "update mydataset.mytable"])
def test_bq_blocks_mutating_commands(command):
    assert is_safe_bq_command(command) is False
