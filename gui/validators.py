"""Input validation functions for the GUI layer.

Provides validation for port numbers, login form fields, and file/directory paths.
"""

import os


def validate_port(value: str) -> tuple[bool, str]:
    """Validate port string is integer in range 1-65535.

    Args:
        value: The port string to validate.

    Returns:
        Tuple of (is_valid, error_message). If valid, error_message is empty.
    """
    stripped = value.strip()
    if not stripped:
        return False, "Port is required"

    try:
        port = int(stripped)
    except ValueError:
        return False, "Port must be a valid integer"

    if port < 1 or port > 65535:
        return False, "Port must be between 1 and 65535"

    return True, ""


def validate_login_fields(
    host: str, port: str, username: str, password: str
) -> dict[str, str]:
    """Validate all login fields are non-empty and port is valid.

    Args:
        host: The host/IP address string.
        port: The port number string.
        username: The SSH username.
        password: The SSH password.

    Returns:
        Dict of field_name -> error_message for invalid fields.
        Empty dict means all fields are valid.
    """
    errors: dict[str, str] = {}

    if not host or not host.strip():
        errors["host"] = "Host is required"

    if not port or not port.strip():
        errors["port"] = "Port is required"
    else:
        port_valid, port_error = validate_port(port)
        if not port_valid:
            errors["port"] = port_error

    if not username or not username.strip():
        errors["username"] = "Username is required"

    if not password or not password.strip():
        errors["password"] = "Password is required"

    return errors


def validate_paths(
    ap_list_path: str, switch_list_path: str, output_dir: str
) -> dict[str, str]:
    """Validate file/directory paths exist on disk.

    Args:
        ap_list_path: Path to the AP list file.
        switch_list_path: Path to the switch list file.
        output_dir: Path to the output directory.

    Returns:
        Dict of field_name -> error_message for invalid paths.
        Empty dict means all paths are valid.
    """
    errors: dict[str, str] = {}

    if not ap_list_path or not ap_list_path.strip():
        errors["ap_list_path"] = "AP list file path is required"
    elif not os.path.isfile(ap_list_path):
        errors["ap_list_path"] = "AP list file does not exist"

    if not switch_list_path or not switch_list_path.strip():
        errors["switch_list_path"] = "Switch list file path is required"
    elif not os.path.isfile(switch_list_path):
        errors["switch_list_path"] = "Switch list file does not exist"

    if not output_dir or not output_dir.strip():
        errors["output_dir"] = "Output directory path is required"
    elif not os.path.isdir(output_dir):
        errors["output_dir"] = "Output directory does not exist"

    return errors
