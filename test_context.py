import time
import uuid

from proof.core.context import ContextError, ExecutionContext


def test_extraction_and_interpolation():
    print("--- 1. Testing Extraction & String Interpolation ---")
    ctx = ExecutionContext()

    mock_api_response = {
        "status": "success",
        "data": {
            "user_id": 101,
            "profile": {
                "email": "janedoe@example.com"
            }
        },
        "token": "bearer_token_xyz123"
    }

    extraction_rules = {
        "user_id": "$.data.user_id",
        "user_email": "$.data.profile.email",
        "auth_token": "$.token"
    }

    ctx.extract_variables(mock_api_response, extraction_rules)

    print(f"Extracted user_id     : {ctx.get('user_id')} (Type: {type(ctx.get('user_id')).__name__})")
    print(f"Extracted user_email  : {ctx.get('user_email')}")
    print(f"Extracted auth_token  : {ctx.get('auth_token')}")

    raw_user_id = ctx.interpolate_data("${user_id}")
    assert raw_user_id == 101
    assert isinstance(raw_user_id, int)
    print("Type preservation verified: '${user_id}' returned raw integer 101")

    interpolated_path = ctx.interpolate_string("/v1/users/${user_id}/profile")
    assert interpolated_path == "/v1/users/101/profile"
    print(f"Embedded interpolation verified: '{interpolated_path}'")

    request_payload = {
        "headers": {
            "Authorization": "Bearer ${auth_token}"
        },
        "json": {
            "account_id": "${user_id}",
            "contact_email": "${user_email}"
        }
    }
    processed_payload = ctx.interpolate_data(request_payload)
    assert processed_payload["headers"]["Authorization"] == "Bearer bearer_token_xyz123"
    assert processed_payload["json"]["account_id"] == 101  
    assert processed_payload["json"]["contact_email"] == "janedoe@example.com"
    print("Nested payload interpolation verified successfully")


def test_dynamic_variables():
    print("\n--- 2. Testing Built-in Dynamic Generators ---")
    ctx = ExecutionContext()

    generated_uuid = ctx.interpolate_string("${$uuid}")
    val_uuid = uuid.UUID(generated_uuid)
    assert str(val_uuid) == generated_uuid
    print(f"Dynamic $uuid generated   : {generated_uuid}")

    generated_ts = ctx.interpolate_string("${$timestamp}")
    assert isinstance(generated_ts, int)
    assert abs(generated_ts - int(time.time())) <= 2
    print(f"Dynamic $timestamp generated: {generated_ts}")

    generated_rand = ctx.interpolate_string("${$random_int}")
    assert isinstance(generated_rand, int)
    assert 1000 <= generated_rand <= 9999
    print(f"Dynamic $random_int generated: {generated_rand}")

    email_string = ctx.interpolate_string("user_${$timestamp}@test.com")
    assert email_string.startswith("user_") and email_string.endswith("@test.com")
    print(f"Dynamic string embedding : {email_string}")


def test_error_handling():
    print("\n--- 3. Testing Context Error Handling ---")
    ctx = ExecutionContext()

    try:
        ctx.interpolate_string("/api/v1/resource/${missing_var}")
    except ContextError as e:
        print(f"ContextError caught on missing variable: {e}")

    try:
        ctx.extract_variables({"status": "ok"}, {"nonexistent": "$.data.missing_key"})
    except ContextError as e:
        print(f"ContextError caught on failed extraction: {e}")


if __name__ == "__main__":
    print("Executing core/context.py validation suite...\n")
    test_extraction_and_interpolation()
    test_dynamic_variables()
    test_error_handling()
    print("\nAll context & memory tests passed!")
