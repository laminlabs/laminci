from laminci._artifacts import upload_artifact_aws


def test_upload_artifact_aws():
    upload_artifact_aws(type="docs")
