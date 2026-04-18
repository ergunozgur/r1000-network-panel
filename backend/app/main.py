from fastapi import FastAPI, HTTPException, Body
from fastapi.responses import HTMLResponse
from pathlib import Path
import subprocess
import json
import os
import re
import time
import urllib.request
import urllib.error


app = FastAPI(title="R1000 Network Panel")
SERVICE_LAN_DNSMASQ_IPV6_CONF = "/etc/NetworkManager/dnsmasq-shared.d/99-service-lan-ipv6.conf"
PIHOLE_DNSMASQ_FORWARD_CONF = "/etc/NetworkManager/dnsmasq-shared.d/98-pihole-upstream.conf"
HOST_SAMBA_CONFIG_PATHS = [
    "/host/etc/samba/smb.conf",
    "/etc/samba/smb.conf",
]
HOST_SAMBA_MAIN_CONFIG = "/host/etc/samba/smb.conf"
HOST_SAMBA_PORTAL_CONFIG = "/host/etc/samba/portal-shares.conf"
HOST_SAMBA_INCLUDE_LINE = "include = /etc/samba/portal-shares.conf"
RUNTIME_CONFIG_PATH = "/app/data/runtime-config.json"
LTE_APN_PROFILES = [
    {
        "id": "de-telekom-dual",
        "country": "Germany",
        "provider": "Telekom",
        "apn": "internet.telekom",
        "ipv4_method": "auto",
        "ipv6_method": "auto",
        "mccmnc": ["26201"],
    },
    {
        "id": "de-telekom-v6",
        "country": "Germany",
        "provider": "Telekom (IPv6)",
        "apn": "internet.v6.telekom",
        "ipv4_method": "disabled",
        "ipv6_method": "auto",
        "mccmnc": ["26201"],
    },
    {
        "id": "de-vodafone",
        "country": "Germany",
        "provider": "Vodafone DE",
        "apn": "web.vodafone.de",
        "ipv4_method": "auto",
        "ipv6_method": "auto",
        "mccmnc": ["26202"],
    },
    {
        "id": "de-o2",
        "country": "Germany",
        "provider": "O2 / Telefonica DE",
        "apn": "internet",
        "ipv4_method": "auto",
        "ipv6_method": "auto",
        "mccmnc": ["26207", "26203"],
    },
    {
        "id": "tr-turkcell",
        "country": "Turkey",
        "provider": "Turkcell",
        "apn": "internet",
        "ipv4_method": "auto",
        "ipv6_method": "auto",
        "mccmnc": ["28601"],
    },
    {
        "id": "tr-vodafone",
        "country": "Turkey",
        "provider": "Vodafone",
        "apn": "internet",
        "ipv4_method": "auto",
        "ipv6_method": "auto",
        "mccmnc": ["28602"],
    },
    {
        "id": "tr-turk-telekom",
        "country": "Turkey",
        "provider": "Turk Telekom",
        "apn": "internet",
        "ipv4_method": "auto",
        "ipv6_method": "auto",
        "mccmnc": ["28603"],
    },
]
LTE_AUTO_APN = {
    "enabled": True,
    "last_key": "",
    "last_applied": 0.0,
}
LTE_SIM_OVERRIDES: dict[str, dict[str, str]] = {}


def env_flag(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


SERVICE_LAN_INTERFACE = os.getenv("SERVICE_LAN_INTERFACE", "")
SERVICE_LAN_IPV4_GATEWAY = os.getenv("SERVICE_LAN_IPV4_GATEWAY", "192.168.10.1")
SERVICE_LAN_IPV4_SUBNET = os.getenv("SERVICE_LAN_IPV4_SUBNET", "192.168.10.0/24")
SERVICE_LAN_DHCP_RANGE = os.getenv("SERVICE_LAN_DHCP_RANGE", "192.168.10.100-192.168.10.199")
SERVICE_LAN_IPV6_GATEWAY = os.getenv("SERVICE_LAN_IPV6_GATEWAY", "fd42:10::1")
SERVICE_LAN_IPV6_PREFIX = os.getenv("SERVICE_LAN_IPV6_PREFIX", "fd42:10::/64")
SERVICE_LAN_ENABLE_IPV4 = env_flag("SERVICE_LAN_ENABLE_IPV4", True)
SERVICE_LAN_ENABLE_IPV6 = env_flag("SERVICE_LAN_ENABLE_IPV6", True)
SERVICE_LAN_ROLE = os.getenv("SERVICE_LAN_ROLE", "isolated")
SERVICE_LAN_DNS_SERVERS = os.getenv("SERVICE_LAN_DNS_SERVERS", LAN_DNS_SERVERS if "LAN_DNS_SERVERS" in globals() else "1.1.1.1,8.8.8.8")
SERVICE_LAN_DNS_SEARCH = os.getenv("SERVICE_LAN_DNS_SEARCH", LAN_DNS_SEARCH if "LAN_DNS_SEARCH" in globals() else "home.lab")
FALLBACK_SERVICE_LAN_INTERFACE = "enx2cf7f1232c1a"
LAN_PROFILE_NAME = os.getenv("LAN_PROFILE_NAME", "Home Lab LAN")
LAN_TARGET_INTERFACE = os.getenv("LAN_TARGET_INTERFACE", "eth0")
LAN_ROLE = os.getenv("LAN_ROLE", "multi-purpose")
LAN_IPV4_MODE = os.getenv("LAN_IPV4_MODE", "shared")
LAN_IPV4_ADDRESS = os.getenv("LAN_IPV4_ADDRESS", "10.0.0.1/24")
LAN_IPV4_SUBNET = os.getenv("LAN_IPV4_SUBNET", "10.0.0.0/24")
LAN_DHCP_RANGE = os.getenv("LAN_DHCP_RANGE", "10.0.0.100-10.0.0.199")
LAN_IPV6_MODE = os.getenv("LAN_IPV6_MODE", "routed")
LAN_IPV6_ADDRESS = os.getenv("LAN_IPV6_ADDRESS", "fd42:100::1/64")
LAN_IPV6_PREFIX = os.getenv("LAN_IPV6_PREFIX", "fd42:100::/64")
LAN_DNS_SERVERS = os.getenv("LAN_DNS_SERVERS", "1.1.1.1,8.8.8.8")
LAN_DNS_SEARCH = os.getenv("LAN_DNS_SEARCH", "home.lab")
LAN_ROLE_OPTIONS = ["isolated", "internal", "external"]
MAIN_LAN_CONFIG = {
    "name": "Main LAN",
    "target_interface": LAN_TARGET_INTERFACE,
    "role": LAN_ROLE,
    "ipv4_mode": LAN_IPV4_MODE,
    "ipv4_address": LAN_IPV4_ADDRESS,
    "ipv4_subnet": LAN_IPV4_SUBNET,
    "dhcp_range": LAN_DHCP_RANGE,
    "ipv6_mode": LAN_IPV6_MODE,
    "ipv6_address": LAN_IPV6_ADDRESS,
    "ipv6_prefix": LAN_IPV6_PREFIX,
    "dns_servers": LAN_DNS_SERVERS,
    "dns_search": LAN_DNS_SEARCH,
}
SERVICE_LAN_CONFIG = {
    "name": "Service LAN",
    "interface": SERVICE_LAN_INTERFACE,
    "role": SERVICE_LAN_ROLE,
    "ipv4_gateway": SERVICE_LAN_IPV4_GATEWAY,
    "ipv4_subnet": SERVICE_LAN_IPV4_SUBNET,
    "dhcp_range": SERVICE_LAN_DHCP_RANGE,
    "ipv6_gateway": SERVICE_LAN_IPV6_GATEWAY,
    "ipv6_prefix": SERVICE_LAN_IPV6_PREFIX,
    "enable_ipv4": "true" if SERVICE_LAN_ENABLE_IPV4 else "false",
    "enable_ipv6": "true" if SERVICE_LAN_ENABLE_IPV6 else "false",
    "dns_servers": SERVICE_LAN_DNS_SERVERS,
    "dns_search": SERVICE_LAN_DNS_SEARCH,
}
WIFI_CONFIG = {
    "interface": os.getenv("WIFI_INTERFACE", "wlan0"),
    "mode": os.getenv("WIFI_MODE", "client"),
    "ssid": os.getenv("WIFI_SSID", ""),
    "password": os.getenv("WIFI_PASSWORD", ""),
    "hotspot_ssid": os.getenv("WIFI_HOTSPOT_SSID", "R1000-Hotspot"),
    "hotspot_password": os.getenv("WIFI_HOTSPOT_PASSWORD", "changeme123"),
    "hotspot_security": os.getenv("WIFI_HOTSPOT_SECURITY", "wpa2-personal"),
    "ipv4_method": os.getenv("WIFI_IPV4_METHOD", "auto"),
    "ipv4_address": os.getenv("WIFI_IPV4_ADDRESS", ""),
    "ipv6_method": os.getenv("WIFI_IPV6_METHOD", "disabled"),
    "ipv6_address": os.getenv("WIFI_IPV6_ADDRESS", ""),
}
WIFI_SECRET_KEYS = {"password", "hotspot_password"}


def runtime_config_snapshot() -> dict[str, object]:
    wifi_persisted = {
        key: value
        for key, value in WIFI_CONFIG.items()
        if key not in WIFI_SECRET_KEYS
    }
    return {
        "main_lan": dict(MAIN_LAN_CONFIG),
        "service_lan": dict(SERVICE_LAN_CONFIG),
        "wifi": wifi_persisted,
        "lte": {
            "auto_apn_enabled": LTE_AUTO_APN["enabled"],
            "sim_overrides": dict(LTE_SIM_OVERRIDES),
        },
    }


def save_runtime_config() -> None:
    path = Path(RUNTIME_CONFIG_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(runtime_config_snapshot(), indent=2))


def load_runtime_config() -> None:
    raw = read_text(RUNTIME_CONFIG_PATH, "")
    if not raw:
        return
    try:
        data = json.loads(raw)
    except Exception:
        return

    for key, value in data.get("main_lan", {}).items():
        if key in MAIN_LAN_CONFIG and isinstance(value, str):
            MAIN_LAN_CONFIG[key] = value.strip()
    MAIN_LAN_CONFIG["role"] = normalize_lan_role(MAIN_LAN_CONFIG.get("role", "internal"))
    for key, value in data.get("service_lan", {}).items():
        if key in SERVICE_LAN_CONFIG and isinstance(value, str):
            SERVICE_LAN_CONFIG[key] = value.strip()
    SERVICE_LAN_CONFIG["role"] = normalize_lan_role(SERVICE_LAN_CONFIG.get("role", "isolated"))
    for key, value in data.get("wifi", {}).items():
        if key in WIFI_CONFIG and key not in WIFI_SECRET_KEYS and isinstance(value, str):
            WIFI_CONFIG[key] = value.strip()
    if WIFI_CONFIG.get("mode") == "hotspot" and WIFI_CONFIG.get("ipv6_method") == "auto":
        WIFI_CONFIG["ipv6_method"] = "disabled"
    lte_data = data.get("lte", {})
    auto_apn_enabled = lte_data.get("auto_apn_enabled")
    if isinstance(auto_apn_enabled, bool):
        LTE_AUTO_APN["enabled"] = auto_apn_enabled
    sim_overrides = lte_data.get("sim_overrides", {})
    if isinstance(sim_overrides, dict):
        LTE_SIM_OVERRIDES.clear()
        for sim_key, override in sim_overrides.items():
            if not isinstance(sim_key, str) or not isinstance(override, dict):
                continue
            sanitized = {}
            for key in ("id", "apn", "ipv4_method", "ipv6_method"):
                value = override.get(key, "")
                if isinstance(value, str):
                    sanitized[key] = value.strip()
            if sanitized.get("apn"):
                LTE_SIM_OVERRIDES[sim_key] = sanitized


def read_text(path: str, default: str = "") -> str:
    try:
        return Path(path).read_text().strip()
    except Exception:
        return default


def run_command(cmd: list[str]) -> str:
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return result.stdout.strip()
    except Exception:
        return ""


def run_command_full(cmd: list[str], env: dict[str, str] | None = None) -> tuple[int, str, str]:
    try:
        merged_env = os.environ.copy()
        if env:
            merged_env.update(env)
        result = subprocess.run(cmd, capture_output=True, text=True, env=merged_env)
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except Exception as exc:
        return 1, "", str(exc)


def run_command_input(cmd: list[str], input_text: str) -> tuple[int, str, str]:
    try:
        result = subprocess.run(cmd, input=input_text, capture_output=True, text=True)
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except Exception as exc:
        return 1, "", str(exc)


def host_nmcli_command(args: list[str]) -> list[str]:
    return ["chroot", "/host", "/usr/bin/nmcli"] + args


def host_nmcli_available() -> bool:
    return Path("/host/usr/bin/nmcli").exists()


def nmcli_command(args: list[str]) -> list[str]:
    return host_nmcli_command(args) if host_nmcli_available() else ["nmcli"] + args


def nmcli_available() -> bool:
    return host_nmcli_available() or command_exists("nmcli")


def run_nmcli(args: list[str]) -> str:
    return run_command(nmcli_command(args))


def run_nmcli_full(args: list[str]) -> tuple[int, str, str]:
    return run_command_full(nmcli_command(args))


def host_command_available(path: str) -> bool:
    return Path("/host").joinpath(path.lstrip("/")).exists()


def host_binary_command(path: str, args: list[str]) -> list[str]:
    return ["chroot", "/host", path] + args


def command_exists(name: str) -> bool:
    result = subprocess.run(["which", name], capture_output=True, text=True)
    return result.returncode == 0


def slugify(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_]+", "_", value).strip("_").lower()


def lan_cfg(key: str) -> str:
    return str(MAIN_LAN_CONFIG.get(key, ""))


def service_lan_cfg(key: str) -> str:
    return str(SERVICE_LAN_CONFIG.get(key, ""))


def wifi_cfg(key: str) -> str:
    return str(WIFI_CONFIG.get(key, ""))


def same_physical_lan_interface(main_interface: str, service_interface: str) -> bool:
    return bool(main_interface and service_interface and main_interface == service_interface)


def normalize_lan_role(value: str) -> str:
    role = (value or "").strip().lower()
    mapping = {
        "multi-purpose": "internal",
        "home-lab": "internal",
        "service": "external",
        "isolated": "isolated",
        "internal": "internal",
        "external": "external",
    }
    return mapping.get(role, "internal")


def role_description(role: str) -> str:
    normalized = normalize_lan_role(role)
    if normalized == "isolated":
        return "internet only for clients, no internal LAN access"
    if normalized == "external":
        return "internet-facing client zone, kept away from internal LAN but still reachable from Tailscale on the router"
    return "trusted internal LAN with access to local services and management"


def read_millicelsius(path: str) -> float | None:
    raw = read_text(path, "")
    if not raw:
        return None
    try:
        value = int(raw)
    except ValueError:
        return None
    return round(value / 1000.0, 1)


def fetch_node_exporter_metrics() -> str:
    try:
        with urllib.request.urlopen("http://127.0.0.1:9100/metrics", timeout=1.5) as response:
            return response.read().decode("utf-8", errors="ignore")
    except Exception:
        return ""


def metric_value(metrics_text: str, pattern: str) -> float | None:
    match = re.search(pattern, metrics_text, re.MULTILINE)
    if not match:
        return None
    try:
        return round(float(match.group(1)), 1)
    except ValueError:
        return None


def get_cpu_temperature_c() -> float | None:
    metrics = fetch_node_exporter_metrics()
    value = metric_value(
        metrics,
        r'^node_hwmon_temp_celsius\{[^}]*chip="thermal_thermal_zone0"[^}]*\}\s+([0-9.]+)$',
    )
    if value is not None:
        return value
    base = Path("/sys/class/thermal")
    if not base.exists():
        return None
    for zone in sorted(base.glob("thermal_zone*")):
        zone_type = read_text(str(zone / "type"), "").lower()
        if "cpu" in zone_type:
            value = read_millicelsius(str(zone / "temp"))
            if value is not None:
                return value
    for zone in sorted(base.glob("thermal_zone*")):
        value = read_millicelsius(str(zone / "temp"))
        if value is not None:
            return value
    return None


def get_nvme_temperature_c() -> float | None:
    metrics = fetch_node_exporter_metrics()
    value = metric_value(
        metrics,
        r'^node_hwmon_temp_celsius\{[^}]*chip="nvme_nvme0"[^}]*\}\s+([0-9.]+)$',
    )
    if value is not None:
        return value
    value = metric_value(metrics, r'^edge_nvme_temp_c\s+([0-9.]+)$')
    if value is not None:
        return value
    candidates = list(Path("/sys/class/nvme").glob("nvme*/device/hwmon/hwmon*/temp1_input"))
    for candidate in candidates:
        value = read_millicelsius(str(candidate))
        if value is not None:
            return value
    return None


def get_input_voltage_v() -> float | None:
    for candidate in Path("/sys/class/power_supply").glob("*/voltage_now"):
        raw = read_text(str(candidate), "")
        if not raw:
            continue
        try:
            return round(int(raw) / 1_000_000.0, 2)
        except ValueError:
            continue
    return None


load_runtime_config()
save_runtime_config()


def is_process_running(name: str) -> bool:
    result = subprocess.run(["pgrep", "-x", name], capture_output=True, text=True)
    return result.returncode == 0


def clean_ansi(text: str) -> str:
    return re.sub(r"\x1B\[[0-9;]*[A-Za-z]", "", text).strip()


def parse_mmcli_value(text: str, label: str) -> str:
    pattern = rf"{re.escape(label)}\s*:\s*(.+)"
    match = re.search(pattern, text)
    return match.group(1).strip() if match else ""


def get_modem_id() -> str:
    output = run_command(["mmcli", "-L"])
    match = re.search(r"/Modem/(\d+)", output)
    return match.group(1) if match else ""


def get_operator_info(modem_id: str) -> dict[str, str]:
    info = {"mcc": "", "mnc": "", "operator_name": ""}
    if not modem_id:
        return info
    data = run_command(["mmcli", "-m", modem_id, "--3gpp"])
    if not data:
        return info
    info["operator_name"] = clean_ansi(parse_mmcli_value(data, "operator name"))
    info["mcc"] = clean_ansi(parse_mmcli_value(data, "operator mcc"))
    info["mnc"] = clean_ansi(parse_mmcli_value(data, "operator mnc"))
    return info


def get_sim_imsi(modem_id: str) -> str:
    if not modem_id:
        return ""
    modem = run_command(["mmcli", "-m", modem_id])
    sim_path = clean_ansi(parse_mmcli_value(modem, "primary sim path"))
    match = re.search(r"/SIM/(\d+)", sim_path)
    if not match:
        return ""
    sim_id = match.group(1)
    sim_info = run_command(["mmcli", "-i", sim_id])
    return clean_ansi(parse_mmcli_value(sim_info, "imsi"))


def get_active_cellular_connection() -> str:
    output = run_nmcli(["-t", "-f", "NAME,TYPE,DEVICE", "connection", "show", "--active"])
    if not output:
        return ""
    for line in output.splitlines():
        parts = line.split(":")
        if len(parts) >= 2 and parts[1] == "gsm":
            return parts[0]
    return ""


def suggest_apn_profile(operator: dict[str, str]) -> dict[str, str] | None:
    key = f"{operator.get('mcc', '')}{operator.get('mnc', '')}".strip()
    if key:
        for item in LTE_APN_PROFILES:
            if key in item.get("mccmnc", []):
                return item
    name = operator.get("operator_name", "").lower()
    if name:
        for item in LTE_APN_PROFILES:
            if item["provider"].lower() in name:
                return item
    return None


def ensure_auto_apn() -> None:
    if not LTE_AUTO_APN["enabled"]:
        return
    modem_id = get_modem_id()
    operator = get_operator_info(modem_id)
    sim_imsi = get_sim_imsi(modem_id)
    sim_key = sim_imsi or f"{operator.get('mcc', '')}{operator.get('mnc', '')}".strip()
    override = LTE_SIM_OVERRIDES.get(sim_key, {})
    if override.get("apn"):
        profile = override
    else:
        profile = suggest_apn_profile(operator)
    if not profile:
        return
    key = profile.get("id", profile.get("apn", ""))
    now = time.time()
    if LTE_AUTO_APN["last_key"] == key and (now - LTE_AUTO_APN["last_applied"]) < 20:
        return
    conn = get_active_cellular_connection()
    if not conn:
        return
    current_apn = run_nmcli(["-g", "gsm.apn", "connection", "show", conn])
    current_v4 = run_nmcli(["-g", "ipv4.method", "connection", "show", conn])
    current_v6 = run_nmcli(["-g", "ipv6.method", "connection", "show", conn])
    if current_apn == profile["apn"] and current_v4 == profile["ipv4_method"] and current_v6 == profile["ipv6_method"]:
        return
    run_nmcli_full(["connection", "modify", conn, "gsm.apn", profile["apn"], "ipv4.method", profile["ipv4_method"], "ipv6.method", profile["ipv6_method"]])
    run_nmcli_full(["connection", "down", conn])
    run_nmcli_full(["connection", "up", conn])
    LTE_AUTO_APN["last_key"] = key
    LTE_AUTO_APN["last_applied"] = now


def parse_samba_shares(conf_text: str, source: str) -> list[dict[str, str]]:
    shares: list[dict[str, str]] = []
    current_name = ""
    current_share: dict[str, str] | None = None
    for raw_line in conf_text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or line.startswith(";"):
            continue
        if line.startswith("[") and line.endswith("]"):
            if current_share and current_name and current_name.lower() != "global":
                shares.append(current_share)
            current_name = line[1:-1].strip()
            current_share = {
                "name": current_name,
                "path": "",
                "read_only": "",
                "guest_ok": "",
                "valid_users": "",
                "source": source,
            }
            continue
        if "=" not in line or not current_share:
            continue
        key, value = [part.strip() for part in line.split("=", 1)]
        key = key.lower()
        if key == "path":
            current_share["path"] = value
        elif key == "read only":
            current_share["read_only"] = value
        elif key == "guest ok":
            current_share["guest_ok"] = value
        elif key == "valid users":
            current_share["valid_users"] = value

    if current_share and current_name and current_name.lower() != "global":
        shares.append(current_share)
    return shares


def ensure_samba_portal_include() -> None:
    main_path = Path(HOST_SAMBA_MAIN_CONFIG)
    if not main_path.exists():
        raise HTTPException(status_code=500, detail="Host Samba config not found")
    text = main_path.read_text()
    if HOST_SAMBA_INCLUDE_LINE in text:
        return
    lines = text.splitlines()
    inserted = False
    for index, line in enumerate(lines):
        if line.strip().lower() == "[global]":
            insert_at = index + 1
            while insert_at < len(lines) and lines[insert_at].startswith(("\t", " ")):
                insert_at += 1
            lines.insert(insert_at, f"\t{HOST_SAMBA_INCLUDE_LINE}")
            inserted = True
            break
    if not inserted:
        lines.extend(["", "[global]", f"\t{HOST_SAMBA_INCLUDE_LINE}"])
    main_path.write_text("\n".join(lines).rstrip() + "\n")


def read_portal_samba_shares() -> list[dict[str, str]]:
    return parse_samba_shares(read_text(HOST_SAMBA_PORTAL_CONFIG, ""), "portal")


def write_portal_samba_shares(shares: list[dict[str, str]]) -> None:
    lines = ["# Managed by Network Panel", ""]
    for share in shares:
        lines.append(f"[{share['name']}]")
        lines.append(f"\tpath = {share['path']}")
        lines.append(f"\tread only = {share['read_only'] or 'No'}")
        lines.append(f"\tguest ok = {share['guest_ok'] or 'No'}")
        if share.get("valid_users"):
            lines.append(f"\tvalid users = {share['valid_users']}")
        lines.append("")
    Path(HOST_SAMBA_PORTAL_CONFIG).write_text("\n".join(lines).rstrip() + "\n")


def test_samba_config() -> None:
    code, stdout, stderr = run_command_full(["testparm", "-s", HOST_SAMBA_MAIN_CONFIG])
    if code != 0:
        raise HTTPException(status_code=500, detail={"code": code, "stdout": stdout, "stderr": stderr or "Samba config validation failed"})


def get_samba_users() -> list[dict[str, str]]:
    if not host_command_available("/usr/bin/pdbedit"):
        return []
    code, stdout, _ = run_command_full(host_binary_command("/usr/bin/pdbedit", ["-L"]))
    if code != 0:
        return []
    users: list[dict[str, str]] = []
    for line in stdout.splitlines():
        if not line.strip():
            continue
        username, _, description = line.partition(":")
        users.append(
            {
                "username": username.strip(),
                "description": description.strip(),
            }
        )
    return users


def get_printing_status() -> dict[str, object]:
    listeners = parse_service_listeners()
    cups_listener = any("631" in (svc.get("ports") or []) for svc in listeners)
    samba = get_samba_status()
    printer_shares = [share for share in samba.get("shares", []) if share.get("name", "").lower() in {"printers", "print$"}]
    cups_installed = host_command_available("/usr/bin/systemctl")
    cups_enabled = False
    cups_active = is_process_running("cupsd")
    if cups_installed:
        _, enabled_out, enabled_err = run_command_full(host_binary_command("/usr/bin/systemctl", ["is-enabled", "cups"]))
        _, active_out, active_err = run_command_full(host_binary_command("/usr/bin/systemctl", ["is-active", "cups"]))
        if "not-found" in (enabled_out + enabled_err + active_out + active_err):
            cups_installed = False
        else:
            cups_enabled = enabled_out.strip() == "enabled"
            cups_active = active_out.strip() == "active" or cups_active
    return {
        "cups_installed": cups_installed,
        "cups_enabled": cups_enabled,
        "cups_active": cups_active,
        "cups_listener": cups_listener,
        "printer_shares": printer_shares,
    }


def get_samba_status() -> dict[str, object]:
    smbd = is_process_running("smbd")
    nmbd = is_process_running("nmbd")
    conf_path = ""
    conf_text = ""
    for candidate in HOST_SAMBA_CONFIG_PATHS:
        conf_text = read_text(candidate, "")
        if conf_text:
            conf_path = candidate
            break

    shares = parse_samba_shares(conf_text, "main")
    portal_shares = read_portal_samba_shares()
    combined_shares = shares + [
        share for share in portal_shares
        if all(existing["name"].lower() != share["name"].lower() for existing in shares)
    ]

    return {
        "running": smbd,
        "nmbd_running": nmbd,
        "config_path": conf_path or "not found",
        "shares": combined_shares,
        "portal_shares": portal_shares,
        "users": get_samba_users(),
        "host_config_writable": Path("/host/etc/samba").exists() and os.access("/host/etc/samba", os.W_OK),
        "smbpasswd_available": command_exists("smbpasswd"),
    }


def get_service_lan_connection_mode() -> str:
    ruleset = run_command(["nft", "list", "ruleset"])
    interface = get_service_lan_interface(ruleset)
    if interface and has_nft_table(ruleset, "ip", f"nm-shared-{interface}"):
        return "shared"
    return "manual"


def dhcp_listener_active() -> bool:
    output = run_command(["ss", "-ulpn"])
    if not output:
        return False

    for line in output.splitlines():
        if ":67 " in line or line.endswith(":67"):
            return True
    return False


def ipv6_ra_active() -> bool:
    return (
        is_process_running("service-lan-ra.py")
        or (
            is_process_running("dnsmasq")
            and Path(SERVICE_LAN_DNSMASQ_IPV6_CONF).exists()
            and "enable-ra" in read_text(SERVICE_LAN_DNSMASQ_IPV6_CONF)
        )
    )


def forwarding_active(family: int) -> bool:
    if family == 4:
        return read_text("/proc/sys/net/ipv4/ip_forward", "0") == "1"
    if family == 6:
        return read_text("/proc/sys/net/ipv6/conf/all/forwarding", "0") == "1"
    return False


def interface_ipv6_disabled(interface: str) -> bool:
    return read_text(f"/proc/sys/net/ipv6/conf/{interface}/disable_ipv6", "1") == "1"


def has_default_route(family: int) -> bool:
    if family == 4:
        return bool(run_command(["ip", "route", "show", "default"]))
    if family == 6:
        return bool(run_command(["ip", "-6", "route", "show", "default"]))
    return False


def has_nft_table(ruleset: str, family: str, name: str) -> bool:
    pattern = rf"(^|\n)table\s+{re.escape(family)}\s+{re.escape(name)}\s*\{{"
    return re.search(pattern, ruleset) is not None


def detect_shared_interfaces(ruleset: str) -> list[str]:
    return re.findall(r"table\s+ip\s+nm-shared-([^\s{]+)", ruleset)


def get_service_lan_interface(ruleset: str = "") -> str:
    _, resolved = resolve_lan_interfaces()
    if resolved:
        return resolved

    if not ruleset:
        ruleset = run_command(["nft", "list", "ruleset"])

    shared = detect_shared_interfaces(ruleset)
    if shared:
        return shared[0]

    return FALLBACK_SERVICE_LAN_INTERFACE


def parse_service_listeners() -> list[dict[str, object]]:
    output = run_command(["ss", "-H", "-ltnup"])
    if not output:
        return []

    port_names = {
        "22": "SSH",
        "53": "DNS",
        "67": "DHCP",
        "80": "HTTP",
        "137": "NetBIOS",
        "138": "NetBIOS Datagram",
        "139": "Samba",
        "445": "Samba",
        "3000": "Grafana",
        "7575": "VirtualHere",
        "8080": "Network Panel",
        "8081": "Pi-hole",
        "9000": "Portainer",
        "9090": "Cockpit",
        "9091": "Prometheus",
        "9100": "Node Exporter",
        "9443": "Portainer HTTPS",
        "41641": "Tailscale",
    }

    services: dict[tuple[str, str], dict[str, object]] = {}
    for line in output.splitlines():
        parts = line.split()
        if len(parts) < 5:
            continue

        proto = parts[0]
        local = parts[4]
        if local.startswith("["):
            host_part, _, port = local.rpartition(":")
            host = host_part.strip("[]")
        else:
            host, _, port = local.rpartition(":")

        if not port:
            continue

        name = port_names.get(port, f"Port {port}")
        key = (name, proto)
        service = services.setdefault(
            key,
            {"name": name, "type": "listener", "active": True, "ports": set(), "binds": set()},
        )
        service["ports"].add(f"{proto}/{port}")
        service["binds"].add(host or "*")

    result = []
    for service in sorted(services.values(), key=lambda item: item["name"]):
        result.append(
            {
                "name": service["name"],
                "type": service["type"],
                "active": service["active"],
                "ports": sorted(service["ports"]),
                "binds": sorted(service["binds"]),
            }
        )

    return result


def known_port_names() -> dict[str, str]:
    return {
        "22": "SSH",
        "53": "DNS",
        "67": "DHCP",
        "80": "HTTP",
        "137": "NetBIOS",
        "138": "NetBIOS Datagram",
        "139": "Samba",
        "445": "Samba",
        "3000": "Grafana",
        "7575": "VirtualHere",
        "8080": "Network Panel",
        "8081": "Pi-hole",
        "9000": "Portainer",
        "9090": "Cockpit",
        "9091": "Prometheus",
        "9100": "Node Exporter",
        "9443": "Portainer HTTPS",
        "20211": "NetAlertX",
        "41641": "Tailscale",
    }


def local_http_probe(url: str, timeout: float = 3.0) -> dict[str, object]:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            return {"ok": True, "code": getattr(response, "status", 200), "url": url}
    except urllib.error.HTTPError as exc:
        return {"ok": True, "code": exc.code, "url": url}
    except Exception as exc:
        return {"ok": False, "code": 0, "url": url, "error": str(exc)}


def get_pihole_container_ip() -> str:
    docker_cmd = None
    if host_command_available("/usr/bin/docker"):
        docker_cmd = host_binary_command(
            "/usr/bin/docker",
            [
                "inspect",
                "-f",
                "{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}",
                "pihole",
            ],
        )
    elif command_exists("docker"):
        docker_cmd = [
            "docker",
            "inspect",
            "-f",
            "{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}",
            "pihole",
        ]
    if not docker_cmd:
        return ""
    code, stdout, stderr = run_command_full(docker_cmd)
    if code != 0:
        return ""
    candidate = stdout.strip()
    if re.fullmatch(r"\d+\.\d+\.\d+\.\d+", candidate):
        return candidate
    return ""


def pihole_forwarding_enabled() -> bool:
    config = read_text(PIHOLE_DNSMASQ_FORWARD_CONF, "")
    ip = get_pihole_container_ip()
    if not config or not ip:
        return False
    return f"server={ip}" in config


def configure_pihole_dns_forwarding() -> tuple[int, str, str]:
    pihole_ip = get_pihole_container_ip()
    if not pihole_ip:
        return 1, "", "Pi-hole container IP not found"

    contents = (
        "# Managed by network-panel\n"
        "# Forward shared dnsmasq queries into Pi-hole so FTL sees and blocks LAN traffic.\n"
        "no-resolv\n"
        "cache-size=0\n"
        f"server={pihole_ip}\n"
    )
    try:
        Path(PIHOLE_DNSMASQ_FORWARD_CONF).write_text(contents)
    except Exception as exc:
        return 1, "", f"Failed to write {PIHOLE_DNSMASQ_FORWARD_CONF}: {exc}"

    outputs = []
    errors = []
    for connection in ("main-lan", "portal-hotspot"):
        code, stdout, stderr = run_nmcli_full(["connection", "show", connection])
        if code != 0:
            continue
        down_code, down_stdout, down_stderr = run_nmcli_full(["connection", "down", connection])
        up_code, up_stdout, up_stderr = run_nmcli_full(["connection", "up", connection])
        if down_stdout:
            outputs.append(down_stdout)
        if up_stdout:
            outputs.append(up_stdout)
        if down_stderr:
            errors.append(down_stderr)
        if up_stderr:
            errors.append(up_stderr)
        if up_code != 0:
            return up_code, "\n".join(outputs).strip(), "\n".join(errors).strip()

    return 0, "\n".join(outputs).strip(), "\n".join(errors).strip()


def get_pihole_status() -> dict[str, object]:
    listeners = parse_service_listeners()
    services_by_name = {service["name"]: service for service in listeners}
    pihole_listener = services_by_name.get("Pi-hole", {})
    dns_listener = services_by_name.get("DNS", {})
    admin_probe = local_http_probe("http://127.0.0.1:8081/admin/")
    root_probe = local_http_probe("http://127.0.0.1:8081/")
    dns_binds = [
        bind for bind in dns_listener.get("binds", [])
        if bind not in {"127.0.0.53%lo", "127.0.0.54", "::1"}
    ]
    main_ipv4 = get_main_lan_ipv4()
    service_ipv4 = service_lan_cfg("ipv4_gateway")
    wifi_ipv4 = get_wifi_status().get("device", {}).get("ipv4", [])
    wifi_bind = wifi_ipv4[0] if wifi_ipv4 else ""
    active_networks = []
    if main_ipv4 and main_ipv4 in dns_binds:
        active_networks.append("Main LAN")
    if service_ipv4 and service_ipv4 in dns_binds:
        active_networks.append("Service LAN")
    if wifi_bind and wifi_bind in dns_binds:
        active_networks.append("Wi-Fi Hotspot")
    pihole_ip = get_pihole_container_ip()
    forwarding_enabled = pihole_forwarding_enabled()
    return {
        "active": bool(pihole_listener) or admin_probe["ok"],
        "web_port": "8081",
        "admin_reachable": admin_probe["ok"],
        "admin_status_code": admin_probe.get("code", 0),
        "root_reachable": root_probe["ok"],
        "root_status_code": root_probe.get("code", 0),
        "dns_listener_detected": bool(dns_listener),
        "dns_binds": dns_binds,
        "container_ip": pihole_ip,
        "dns_forwarding_enabled": forwarding_enabled,
        "active_networks": active_networks,
        "notes": [
            "Main LAN and Wi-Fi hotspot clients use the local gateway as DNS in shared mode",
            "Shared dnsmasq needs forwarding into Pi-hole for query statistics and blocking to appear in FTL",
        ],
    }


@app.post("/api/pihole/activate")
def pihole_activate():
    status = get_pihole_status()
    if not status.get("active") or not status.get("dns_listener_detected"):
        raise HTTPException(status_code=500, detail="Pi-hole DNS is not ready")
    code, stdout, stderr = configure_pihole_dns_forwarding()
    if code != 0:
        raise HTTPException(
            status_code=500,
            detail={"code": code, "stdout": stdout, "stderr": stderr or "Failed to forward shared DNS into Pi-hole"},
        )
    main_ipv4 = get_main_lan_ipv4()
    if main_ipv4:
        MAIN_LAN_CONFIG["dns_servers"] = main_ipv4
    service_ipv4 = service_lan_cfg("ipv4_gateway")
    if service_ipv4:
        SERVICE_LAN_CONFIG["dns_servers"] = service_ipv4
    save_runtime_config()
    return {
        "ok": True,
        "main_lan_dns": MAIN_LAN_CONFIG.get("dns_servers", ""),
        "service_lan_dns": SERVICE_LAN_CONFIG.get("dns_servers", ""),
        "pihole_forwarding_enabled": pihole_forwarding_enabled(),
        "stdout": stdout,
        "stderr": stderr,
        "active_networks": status.get("active_networks", []),
    }


def get_netalert_status() -> dict[str, object]:
    listeners = parse_service_listeners()
    detected = None
    for service in listeners:
        if service["name"] in {"NetAlertX", "NetAlert"}:
            detected = service
            break
        if "tcp/20211" in service.get("ports", []):
            detected = service
            break

    web_probe = local_http_probe("http://127.0.0.1:20211/")
    return {
        "detected": bool(detected) or web_probe["ok"],
        "web_reachable": web_probe["ok"],
        "status_code": web_probe.get("code", 0),
        "port": "20211",
        "name": detected["name"] if detected else "NetAlertX",
    }


def guess_interface_role(name: str) -> str:
    if name == "lo":
        return "loopback"
    if name.startswith("wwan"):
        return "cellular"
    if name.startswith("wl"):
        return "wifi"
    if name.startswith("tailscale"):
        return "overlay"
    if name.startswith("docker") or name.startswith("br-") or name.startswith("veth"):
        return "container"
    if name.startswith("en") or name.startswith("eth"):
        return "ethernet"
    return "other"


def get_interfaces_data() -> list[dict[str, object]]:
    output = run_command(["ip", "-j", "addr"])
    if not output:
        return []

    try:
        data = json.loads(output)
    except Exception:
        return []

    result = []
    for iface in data:
        name = iface.get("ifname", "")
        if name.startswith("veth") or name.startswith("br-") or name == "docker0":
            continue

        ipv4 = []
        ipv6 = []

        for addr in iface.get("addr_info", []):
            if addr.get("family") == "inet":
                ipv4.append(addr.get("local"))
            elif addr.get("family") == "inet6":
                ipv6.append(addr.get("local"))

        state = iface.get("operstate")
        if state == "UNKNOWN" and (ipv4 or ipv6):
            state = "UP"

        result.append(
            {
                "name": name,
                "state": state,
                "mac": iface.get("address"),
                "ipv4": ipv4,
                "ipv6": ipv6,
                "mtu": iface.get("mtu"),
                "role": guess_interface_role(name),
                "flags": iface.get("flags", []),
                "physical": guess_interface_role(name) in {"ethernet", "wifi", "cellular"},
            }
        )

    return result


def get_interface_data(name: str) -> dict[str, object]:
    for iface in get_interfaces_data():
        if iface["name"] == name:
            return iface
    return {
        "name": name,
        "state": "missing",
        "mac": "",
        "ipv4": [],
        "ipv6": [],
        "mtu": None,
        "role": guess_interface_role(name),
        "flags": [],
    }


def get_main_lan_ipv4() -> str:
    iface = get_interface_data(get_main_lan_interface())
    ipv4 = iface.get("ipv4", [])
    return ipv4[0] if ipv4 else ""


def get_nmcli_device_status(interface: str) -> dict[str, str]:
    if not nmcli_available():
        return {}

    output = run_nmcli(["-t", "-f", "GENERAL.STATE,GENERAL.CONNECTION,GENERAL.TYPE", "device", "show", interface])
    if not output:
        return {}

    status = {}
    for line in output.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        status[key] = value
    return {
        "nm_state": status.get("GENERAL.STATE", ""),
        "nm_connection": status.get("GENERAL.CONNECTION", ""),
        "nm_type": status.get("GENERAL.TYPE", ""),
    }


def get_nmcli_connection_status(connection_name: str) -> dict[str, str]:
    if not nmcli_available():
        return {}

    fields = [
        "connection.id",
        "connection.interface-name",
        "ipv4.method",
        "ipv4.addresses",
        "ipv4.dns",
        "ipv4.dns-search",
        "ipv6.method",
        "ipv6.addresses",
        "ipv6.dns",
    ]
    output = run_nmcli(["-g", ",".join(fields), "connection", "show", connection_name])
    if not output:
        return {}

    values = output.splitlines()
    data = {}
    for index, field in enumerate(fields):
        data[field] = values[index] if index < len(values) else ""
    return data


def get_wifi_radio_state() -> dict[str, str]:
    output = run_nmcli(["radio", "wifi"])
    enabled = output.strip().lower() == "enabled"
    return {"wifi_radio": output.strip() or "unknown", "wifi_radio_enabled": "true" if enabled else "false"}


def humanize_wifi_security(key_mgmt: str, proto: str = "") -> str:
    key = (key_mgmt or "").strip().lower()
    proto_value = (proto or "").strip().upper()
    if not key:
        return "open"
    if key == "wpa-psk":
        return "WPA2-Personal" if "RSN" in proto_value or not proto_value else f"WPA-PSK ({proto_value})"
    if key == "sae":
        return "WPA3-Personal"
    return key_mgmt or "unknown"


def get_wifi_active_connection(interface: str) -> dict[str, str]:
    iface = get_nmcli_device_status(interface)
    connection = iface.get("nm_connection", "")
    if not connection or connection == "--":
        return {}

    fields = [
        "connection.id",
        "connection.interface-name",
        "802-11-wireless.ssid",
        "802-11-wireless.mode",
        "802-11-wireless-security.key-mgmt",
        "802-11-wireless-security.proto",
        "ipv4.method",
        "ipv4.addresses",
        "ipv6.method",
        "ipv6.addresses",
    ]
    output = run_nmcli(["-g", ",".join(fields), "connection", "show", connection])
    if not output:
        return {"connection": connection}

    values = output.splitlines()
    data = {field: values[index] if index < len(values) else "" for index, field in enumerate(fields)}
    mode_map = {"ap": "hotspot", "infrastructure": "client"}
    mode = mode_map.get(data.get("802-11-wireless.mode", ""), data.get("802-11-wireless.mode", ""))
    security = humanize_wifi_security(
        data.get("802-11-wireless-security.key-mgmt", ""),
        data.get("802-11-wireless-security.proto", ""),
    )
    return {
        "connection": data.get("connection.id", connection),
        "ssid": data.get("802-11-wireless.ssid", ""),
        "mode": mode or "unknown",
        "raw_mode": data.get("802-11-wireless.mode", ""),
        "security": security,
        "key_mgmt": data.get("802-11-wireless-security.key-mgmt", ""),
        "ipv4_method": data.get("ipv4.method", ""),
        "ipv4_addresses": data.get("ipv4.addresses", ""),
        "ipv6_method": data.get("ipv6.method", ""),
        "ipv6_addresses": data.get("ipv6.addresses", ""),
    }


def parse_default_route(raw: str) -> dict[str, str]:
    route = {"raw": raw, "via": "", "dev": "", "src": ""}
    if not raw:
        return route

    via = re.search(r"\bvia\s+([^\s]+)", raw)
    dev = re.search(r"\bdev\s+([^\s]+)", raw)
    src = re.search(r"\bsrc\s+([^\s]+)", raw)
    if via:
        route["via"] = via.group(1)
    if dev:
        route["dev"] = dev.group(1)
    if src:
        route["src"] = src.group(1)
    return route


def is_physical_interface(iface: dict[str, object]) -> bool:
    role = iface.get("role")
    return role in {"ethernet", "wifi", "cellular"}


def get_physical_interfaces() -> list[dict[str, object]]:
    return [iface for iface in get_interfaces_data() if is_physical_interface(iface)]


def get_lan_interfaces() -> list[dict[str, object]]:
    result = []
    target_name = get_main_lan_interface()
    service_name = get_service_lan_interface()
    for iface in get_interfaces_data():
        if iface["role"] != "ethernet":
            continue
        if iface["name"] in {target_name, service_name} or iface["state"] == "UP":
            result.append(iface)
    return result


def ethernet_candidates() -> list[dict[str, object]]:
    candidates = [iface for iface in get_interfaces_data() if iface["role"] == "ethernet" and iface["physical"]]
    return sorted(
        candidates,
        key=lambda iface: (
            0 if iface["name"].startswith("eth") else 1,
            0 if iface["state"] == "UP" else 1,
            0 if iface["name"].startswith("enx") else 1,
            iface["name"],
        ),
    )


def choose_interface(preferred: str, exclude: set[str], purpose: str) -> str:
    candidates = ethernet_candidates()
    candidate_names = {iface["name"] for iface in candidates}
    if preferred and preferred in candidate_names and preferred not in exclude:
        return preferred

    if purpose == "service":
        sorted_candidates = sorted(
            candidates,
            key=lambda iface: (
                0 if iface["name"].startswith("enx") else 1,
                0 if iface["state"] == "UP" else 1,
                iface["name"],
            ),
        )
    else:
        sorted_candidates = sorted(
            candidates,
            key=lambda iface: (
                0 if iface["name"].startswith("eth") else 1,
                0 if iface["state"] == "UP" else 1,
                iface["name"],
            ),
        )

    for iface in sorted_candidates:
        if iface["name"] not in exclude:
            return iface["name"]
    return preferred or (sorted_candidates[0]["name"] if sorted_candidates else "")


def resolve_lan_interfaces() -> tuple[str, str]:
    main_preferred = lan_cfg("target_interface")
    service_preferred = service_lan_cfg("interface")
    main_interface = choose_interface(main_preferred, set(), "main")
    service_interface = choose_interface(service_preferred, {main_interface} if main_interface else set(), "service")
    if main_interface == service_interface:
        service_interface = choose_interface("", {main_interface} if main_interface else set(), "service")
    if main_interface == service_interface:
        main_interface = choose_interface("", {service_interface} if service_interface else set(), "main")
    return main_interface, service_interface


def get_main_lan_interface() -> str:
    main_interface, _ = resolve_lan_interfaces()
    return main_interface


def interface_block_table_name(interface: str) -> str:
    return f"portal_block_{slugify(interface)}"


def interface_block_active(ruleset: str, interface: str) -> bool:
    return has_nft_table(ruleset, "inet", interface_block_table_name(interface))


def set_interface_block(interface: str, blocked: bool) -> tuple[int, str, str]:
    table = interface_block_table_name(interface)
    run_command_full(["nft", "delete", "table", "inet", table])
    if not blocked:
        return 0, "", ""

    commands = [
        ["nft", "add", "table", "inet", table],
        ["nft", f"add chain inet {table} forward {{ type filter hook forward priority -5; policy accept; }}"],
        ["nft", "add", "rule", "inet", table, "forward", "iifname", interface, "drop"],
        ["nft", "add", "rule", "inet", table, "forward", "oifname", interface, "drop"],
    ]
    stdout_parts = []
    stderr_parts = []
    for cmd in commands:
        code, stdout, stderr = run_command_full(cmd)
        if stdout:
            stdout_parts.append(stdout)
        if stderr:
            stderr_parts.append(stderr)
        if code != 0:
            return code, "\n".join(stdout_parts), "\n".join(stderr_parts)
    return 0, "\n".join(stdout_parts), "\n".join(stderr_parts)


def parse_ip_neighbors(interface: str, family: str) -> dict[str, dict[str, str]]:
    cmd = ["ip"]
    if family == "ipv6":
        cmd.append("-6")
    cmd.extend(["neigh", "show", "dev", interface])

    neigh_raw = run_command(cmd)
    neighbors = {}
    for line in neigh_raw.splitlines():
        parts = line.split()
        if not parts:
            continue

        address = parts[0]
        state = parts[-1]
        mac = ""
        if "lladdr" in parts:
            lladdr_index = parts.index("lladdr")
            if lladdr_index + 1 < len(parts):
                mac = parts[lladdr_index + 1]

        neighbors[address] = {"mac": mac, "state": state, "family": family, "interface": interface}

    return neighbors


def collect_clients_for_interfaces(interfaces: list[dict[str, object]], default_lease_interface: str) -> list[dict[str, str]]:
    now = int(time.time())
    leases = []
    leases_raw = read_text("/host/var/lib/misc/dnsmasq.leases", "")
    for line in leases_raw.splitlines():
        parts = line.split()
        if len(parts) >= 4:
            try:
                expires_at = int(parts[0])
            except ValueError:
                expires_at = 0
            if expires_at and expires_at < now:
                continue
            leases.append(
                {
                    "expires_at": expires_at,
                    "mac": parts[1].lower(),
                    "ip": parts[2],
                    "hostname": parts[3] if parts[3] != "*" else "",
                    "family": "ipv4",
                    "interface": default_lease_interface,
                }
            )

    lease_by_mac = {}
    for lease in leases:
        current = lease_by_mac.get(lease["mac"])
        if current is None or lease["expires_at"] >= current["expires_at"]:
            lease_by_mac[lease["mac"]] = lease

    result = []
    seen = set()
    for iface in interfaces:
        neighbors = {}
        neighbors.update(parse_ip_neighbors(iface["name"], "ipv4"))
        neighbors.update(parse_ip_neighbors(iface["name"], "ipv6"))
        for address, neigh in neighbors.items():
            mac = (neigh.get("mac") or "").lower()
            lease = lease_by_mac.get(mac, {})
            seen.add((iface["name"], mac, address))
            result.append(
                {
                    "interface": iface["name"],
                    "ip": address,
                    "family": neigh["family"],
                    "mac": neigh.get("mac", ""),
                    "hostname": lease.get("hostname", ""),
                    "state": neigh.get("state", "unknown"),
                }
            )

    for lease in lease_by_mac.values():
        key = (lease["interface"], lease["mac"], lease["ip"])
        if key in seen:
            continue
        result.append(
            {
                "interface": lease["interface"],
                "ip": lease["ip"],
                "family": lease["family"],
                "mac": lease["mac"],
                "hostname": lease["hostname"],
                "state": "lease",
            }
        )

    return result


def get_all_lan_clients() -> list[dict[str, str]]:
    return collect_clients_for_interfaces(get_lan_interfaces(), get_service_lan_interface())


def get_wifi_clients() -> list[dict[str, str]]:
    interface = wifi_cfg("interface")
    active = get_wifi_active_connection(interface)
    if active.get("mode") != "hotspot":
        return []
    wifi_iface = get_interface_data(interface)
    if not wifi_iface.get("name"):
        return []
    clients = collect_clients_for_interfaces([wifi_iface], interface)
    for client in clients:
        client["link"] = "wifi"
    return clients


def get_active_sessions() -> list[dict[str, str]]:
    output = run_command(["ss", "-H", "-tnp", "state", "established"])
    if not output:
        return []

    interfaces = get_interfaces_data()
    ip_to_interface = {}
    for iface in interfaces:
        for addr in iface.get("ipv4", []):
            ip_to_interface[addr] = iface["name"]
        for addr in iface.get("ipv6", []):
            ip_to_interface[addr] = iface["name"]

    port_names = known_port_names()
    sessions = []
    for line in output.splitlines():
        parts = line.split()
        if len(parts) < 4:
            continue
        local = parts[2]
        peer = parts[3]
        process = " ".join(parts[4:]) if len(parts) > 4 else ""
        local_host, _, local_port = local.rpartition(":")
        peer_host, _, peer_port = peer.rpartition(":")
        local_host = local_host.strip("[]")
        peer_host = peer_host.strip("[]")
        if local_host.startswith("127.") or local_host == "::1":
            continue
        entry = port_names.get(local_port, f"Port {local_port}")
        if local_port not in port_names:
            continue
        process_match = re.search(r'"([^"]+)"', process)
        sessions.append(
            {
                "interface": ip_to_interface.get(local_host, "unknown"),
                "local_address": local_host,
                "local_port": local_port,
                "peer_address": peer_host,
                "peer_port": peer_port,
                "service": entry,
                "entry": entry,
                "process": process_match.group(1) if process_match else "",
                "family": "ipv6" if ":" in local_host else "ipv4",
            }
        )
    return sessions


def get_wifi_scan(interface: str, force_rescan: bool = False) -> list[dict[str, str]]:
    if not nmcli_available():
        return []
    if force_rescan:
        run_nmcli_full(["device", "set", interface, "managed", "yes"])
        run_command_full(["ip", "link", "set", "dev", interface, "up"])
        run_nmcli_full(["radio", "wifi", "on"])
        run_nmcli_full(["dev", "wifi", "rescan", "ifname", interface])
    output = run_nmcli(["-t", "-f", "SSID,SIGNAL,SECURITY,IN-USE", "dev", "wifi", "list", "ifname", interface])
    networks = []
    for line in output.splitlines():
        parts = line.split(":")
        if len(parts) < 4:
            continue
        ssid, signal, security, in_use = parts[0], parts[1], parts[2], parts[3]
        if not ssid:
            continue
        networks.append(
            {
                "ssid": ssid,
                "signal": signal,
                "security": security,
                "in_use": in_use == "*",
            }
        )
    return networks


def get_rfkill_status() -> list[dict[str, str]]:
    results = []
    base = Path("/sys/class/rfkill")
    if not base.exists():
        return results
    for entry in base.iterdir():
        rf_type = read_text(str(entry / "type"), "")
        name = read_text(str(entry / "name"), "")
        soft = read_text(str(entry / "soft"), "")
        hard = read_text(str(entry / "hard"), "")
        results.append({"type": rf_type, "name": name, "soft": soft, "hard": hard})
    return results


def get_wifi_status() -> dict[str, object]:
    interface = wifi_cfg("interface")
    iface = get_interface_data(interface)
    iface.update(get_nmcli_device_status(interface))
    iface.update(get_wifi_radio_state())
    active = get_wifi_active_connection(interface)
    clients = get_wifi_clients()
    public_wifi_config = dict(WIFI_CONFIG)
    for key in WIFI_SECRET_KEYS:
        public_wifi_config[key] = ""
    notes = [
        "client mode joins an upstream Wi-Fi network",
        "hotspot mode creates a local AP from wlan0",
    ]
    if active.get("mode") == "hotspot":
        notes.append("hotspot scans are manual to avoid disrupting connected devices")
    if active.get("mode") == "hotspot" and active.get("ipv6_method") == "auto":
        notes.append("hotspot IPv6 auto mode can confuse client captive checks; disabled is usually more stable")
    if iface.get("wifi_radio_enabled") == "false":
        notes.append("Wi-Fi radio is off")
    if iface.get("nm_state", "").startswith("30"):
        notes.append("wlan0 is managed by NetworkManager and ready to scan or connect")
    elif iface.get("nm_state", "").startswith("20"):
        notes.append("wlan0 is visible but still unavailable at the OS or driver level")
    return {
        "interface": interface,
        "config": public_wifi_config,
        "device": iface,
        "active": active,
        "clients": clients,
        "scan": get_wifi_scan(interface, force_rescan=False),
        "rfkill": get_rfkill_status(),
        "notes": notes,
    }


def set_nmcli_managed(interface: str) -> tuple[int, str, str]:
    return run_nmcli_full(["device", "set", interface, "managed", "yes"])


def apply_wifi_mode() -> tuple[int, str, str]:
    interface = wifi_cfg("interface")
    mode = wifi_cfg("mode")
    code, stdout, stderr = set_nmcli_managed(interface)
    if code != 0:
        return code, stdout, stderr

    use_host_nmcli = host_nmcli_available()
    nmcli_cmd = host_nmcli_command if use_host_nmcli else lambda args: ["nmcli"] + args

    if mode == "hotspot":
        connection = "portal-hotspot"
        run_command_full(nmcli_cmd(["connection", "delete", connection]))

        password = wifi_cfg("hotspot_password")
        hotspot_security = wifi_cfg("hotspot_security") or "wpa2-personal"
        if hotspot_security != "open" and len(password) < 8:
            return 1, "", "Hotspot password must be at least 8 characters for WPA2-Personal"
        use_password = hotspot_security != "open" and bool(password)
        if use_password:
            hotspot_args = ["device", "wifi", "hotspot", "ifname", interface, "con-name", connection, "ssid", wifi_cfg("hotspot_ssid"), "password", password]
        else:
            hotspot_args = ["device", "wifi", "hotspot", "ifname", interface, "con-name", connection, "ssid", wifi_cfg("hotspot_ssid")]

        code, stdout, stderr = run_command_full(nmcli_cmd(hotspot_args))
        if code != 0:
            return code, stdout, stderr

        modify_args = [
            "connection", "modify", connection,
            "connection.autoconnect", "yes",
            "ipv4.method", wifi_cfg("ipv4_method") or "shared",
            "ipv6.method", wifi_cfg("ipv6_method") or "disabled",
        ]
        if hotspot_security == "open":
            modify_args.extend(["802-11-wireless-security.key-mgmt", ""])
        code2, stdout2, stderr2 = run_command_full(nmcli_cmd(modify_args))
        if code2 != 0:
            return code2, "\n".join([stdout, stdout2]).strip(), "\n".join([stderr, stderr2]).strip()
        return 0, "\n".join([stdout, stdout2]).strip(), "\n".join([stderr, stderr2]).strip()

    if wifi_cfg("ssid"):
        cmd = nmcli_cmd(["device", "wifi", "connect", wifi_cfg("ssid"), "ifname", interface])
        if wifi_cfg("password"):
            cmd.extend(["password", wifi_cfg("password")])
        return run_command_full(cmd)

    return 1, "", "No Wi-Fi SSID configured"


def set_wifi_power(state: str) -> tuple[int, str, str]:
    interface = wifi_cfg("interface")
    use_host_nmcli = host_nmcli_available()
    nmcli_cmd = host_nmcli_command if use_host_nmcli else lambda args: ["nmcli"] + args

    if state == "off":
        stdout_parts: list[str] = []
        stderr_parts: list[str] = []
        for cmd in (
            nmcli_cmd(["device", "disconnect", interface]),
            ["ip", "link", "set", "dev", interface, "down"],
            nmcli_cmd(["radio", "wifi", "off"]),
        ):
            code, stdout, stderr = run_command_full(cmd)
            if stdout:
                stdout_parts.append(stdout)
            if stderr:
                stderr_parts.append(stderr)
            if code != 0 and "not active" not in stderr.lower():
                return code, "\n".join(stdout_parts).strip(), "\n".join(stderr_parts).strip()
        return 0, "\n".join(stdout_parts).strip(), "\n".join(stderr_parts).strip()

    stdout_parts = []
    stderr_parts = []
    for cmd in (
        nmcli_cmd(["radio", "wifi", "on"]),
        nmcli_cmd(["device", "set", interface, "managed", "yes"]),
        ["ip", "link", "set", "dev", interface, "up"],
    ):
        code, stdout, stderr = run_command_full(cmd)
        if stdout:
            stdout_parts.append(stdout)
        if stderr:
            stderr_parts.append(stderr)
        if code != 0:
            return code, "\n".join(stdout_parts).strip(), "\n".join(stderr_parts).strip()
    return 0, "\n".join(stdout_parts).strip(), "\n".join(stderr_parts).strip()


def configure_main_lan() -> tuple[int, str, str]:
    interface = get_main_lan_interface()
    nmcli_cmd = host_nmcli_command if host_nmcli_available() else (lambda args: ["nmcli"] + args)

    def apply_static_fallback(reason: str) -> tuple[int, str, str]:
        commands = [
            ["ip", "link", "set", "dev", interface, "up"],
            ["ip", "-4", "addr", "flush", "dev", interface],
            ["ip", "-4", "addr", "add", lan_cfg("ipv4_address"), "dev", interface],
        ]
        if lan_cfg("ipv6_mode") != "disabled":
            commands.extend(
                [
                    ["ip", "-6", "addr", "flush", "dev", interface, "scope", "global"],
                    ["ip", "-6", "addr", "add", lan_cfg("ipv6_address"), "dev", interface],
                ]
            )

        stdout_parts = []
        stderr_parts = [reason]
        for cmd in commands:
            code, stdout, stderr = run_command_full(cmd)
            if stdout:
                stdout_parts.append(stdout)
            if stderr:
                stderr_parts.append(stderr)
            if code != 0:
                return code, "\n".join(stdout_parts), "\n".join(stderr_parts)

        stderr_parts.append("Applied static fallback. DHCP/shared automation still needs host-side NetworkManager compatibility.")
        return 0, "\n".join(stdout_parts), "\n".join(stderr_parts)

    if not host_nmcli_available() and not command_exists("nmcli"):
        return apply_static_fallback("nmcli is not available in the backend container")

    connection_name = "main-lan"
    dns_servers = lan_cfg("dns_servers")
    dns_search = lan_cfg("dns_search")

    run_command_full(nmcli_cmd(["device", "set", interface, "managed", "yes"]))

    existing = run_command(nmcli_cmd(["-g", "connection.id", "connection", "show", connection_name]))
    base_cmd = nmcli_cmd(["connection", "modify" if existing else "add"])
    if existing:
        cmd = base_cmd + [connection_name]
    else:
        cmd = base_cmd + ["type", "ethernet", "ifname", interface, "con-name", connection_name]

    settings = [
        "connection.autoconnect", "yes",
        "connection.interface-name", interface,
        "ipv4.method", lan_cfg("ipv4_mode"),
        "ipv4.addresses", lan_cfg("ipv4_address"),
        "ipv6.method", "manual" if lan_cfg("ipv6_mode") != "disabled" else "disabled",
        "ipv6.addresses", lan_cfg("ipv6_address") if lan_cfg("ipv6_mode") != "disabled" else "",
    ]
    if lan_cfg("ipv4_mode") != "shared":
        settings.extend(["ipv4.dns", dns_servers, "ipv4.dns-search", dns_search])
    code, stdout, stderr = run_command_full(cmd + settings)
    if code != 0:
        return apply_static_fallback(stderr or "NetworkManager profile apply failed")

    code, stdout, stderr = run_command_full(nmcli_cmd(["connection", "up", connection_name]))
    if code != 0:
        return apply_static_fallback(stderr or "Failed to bring main-lan up")
    return code, stdout, stderr



@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/overview")
def overview():
    hostname = read_text("/host/etc/hostname", "unknown")

    uptime_raw = read_text("/host/proc/uptime", "0 0").split()
    uptime_seconds = int(float(uptime_raw[0])) if uptime_raw else 0

    default_v4 = run_command(["ip", "route", "show", "default"])
    default_v6 = run_command(["ip", "-6", "route", "show", "default"])

    interfaces_data = get_interfaces_data()
    uplinks = [
        iface for iface in interfaces_data
        if iface["role"] in {"cellular", "wifi", "overlay"} and (iface["ipv4"] or iface["ipv6"] or iface["state"] == "UP")
    ]
    local_lans = [
        iface for iface in interfaces_data
        if iface["role"] == "ethernet"
    ]
    hardware = {
        "cpu_temp_c": get_cpu_temperature_c(),
        "nvme_temp_c": get_nvme_temperature_c(),
        "input_voltage_v": get_input_voltage_v(),
    }

    return {
        "hostname": hostname,
        "uptime_seconds": uptime_seconds,
        "default_route_v4": default_v4,
        "default_route_v6": default_v6,
        "uplink_ipv4": parse_default_route(default_v4),
        "uplink_ipv6": parse_default_route(default_v6),
        "uplinks": uplinks,
        "local_lans": local_lans,
        "hardware": hardware,
    }


@app.get("/api/interfaces")
def interfaces():
    return get_interfaces_data()


@app.get("/api/lte")
def lte():
    modem_id = get_modem_id()
    if not modem_id:
        return {"available": False}

    run_command(["mmcli", "-m", modem_id, "--signal-setup=5"])

    modem = run_command(["mmcli", "-m", modem_id])
    signal = run_command(["mmcli", "-m", modem_id, "--signal-get"])
    operator = get_operator_info(modem_id)

    if not modem:
        return {"available": False}

    ensure_auto_apn()

    return {
        "available": True,
        "state": clean_ansi(parse_mmcli_value(modem, "state")),
        "power_state": clean_ansi(parse_mmcli_value(modem, "power state")),
        "access_tech": clean_ansi(parse_mmcli_value(modem, "access tech")),
        "signal_quality": clean_ansi(parse_mmcli_value(modem, "signal quality")),
        "operator_name": operator.get("operator_name") or clean_ansi(parse_mmcli_value(modem, "operator name")),
        "operator_mcc": operator.get("mcc", ""),
        "operator_mnc": operator.get("mnc", ""),
        "registration": clean_ansi(parse_mmcli_value(modem, "registration")),
        "packet_service_state": clean_ansi(parse_mmcli_value(modem, "packet service state")),
        "rssi": clean_ansi(parse_mmcli_value(signal, "rssi")),
        "rsrq": clean_ansi(parse_mmcli_value(signal, "rsrq")),
        "rsrp": clean_ansi(parse_mmcli_value(signal, "rsrp")),
        "snr": clean_ansi(parse_mmcli_value(signal, "s/n")),
    }


@app.get("/api/lte/profile")
def lte_profile():
    conn = get_active_cellular_connection()
    if not conn:
        return {"available": False, "connection": ""}

    apn = run_nmcli(["-g", "gsm.apn", "connection", "show", conn])
    ipv4_method = run_nmcli(["-g", "ipv4.method", "connection", "show", conn])
    ipv6_method = run_nmcli(["-g", "ipv6.method", "connection", "show", conn])
    return {
        "available": True,
        "connection": conn,
        "apn": apn,
        "ipv4_method": ipv4_method,
        "ipv6_method": ipv6_method,
    }


@app.get("/api/lte/apn/options")
def lte_apn_options():
    return {"options": LTE_APN_PROFILES}


@app.get("/api/lte/apn/suggest")
def lte_apn_suggest():
    modem_id = get_modem_id()
    operator = get_operator_info(modem_id)
    sim_imsi = get_sim_imsi(modem_id)
    sim_key = sim_imsi or f"{operator.get('mcc', '')}{operator.get('mnc', '')}".strip()
    profile = suggest_apn_profile(operator)
    return {
        "operator": operator,
        "suggested": profile or {},
        "sim_key": sim_key,
        "override": LTE_SIM_OVERRIDES.get(sim_key, {}),
    }


@app.get("/api/lte/apn/auto")
def lte_apn_auto_status():
    return {"enabled": LTE_AUTO_APN["enabled"]}


@app.post("/api/lte/apn/auto")
def lte_apn_auto_update(payload: dict = Body(...)):
    enabled = str(payload.get("enabled", "")).strip().lower()
    LTE_AUTO_APN["enabled"] = enabled in {"1", "true", "yes", "on"}
    save_runtime_config()
    return {"ok": True, "enabled": LTE_AUTO_APN["enabled"]}


@app.post("/api/lte/apn/apply")
def lte_apn_apply(payload: dict = Body(...)):
    conn = get_active_cellular_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="No active cellular connection found")

    profile_id = str(payload.get("profile_id", "")).strip()
    custom_apn = str(payload.get("apn", "")).strip()
    ipv4_method = str(payload.get("ipv4_method", "auto")).strip() or "auto"
    ipv6_method = str(payload.get("ipv6_method", "auto")).strip() or "auto"
    remember = str(payload.get("remember", "true")).strip().lower() in {"1", "true", "yes", "on"}

    selected = None
    if profile_id:
        for item in LTE_APN_PROFILES:
            if item["id"] == profile_id:
                selected = item
                break

    if selected:
        apn = selected["apn"]
        ipv4_method = selected["ipv4_method"]
        ipv6_method = selected["ipv6_method"]
    else:
        apn = custom_apn

    if not apn:
        raise HTTPException(status_code=400, detail="APN is required")

    code, stdout, stderr = run_nmcli_full(["connection", "modify", conn, "gsm.apn", apn, "ipv4.method", ipv4_method, "ipv6.method", ipv6_method])
    if code != 0:
        raise HTTPException(status_code=500, detail={"code": code, "stdout": stdout, "stderr": stderr})

    modem_id = get_modem_id()
    operator = get_operator_info(modem_id)
    sim_imsi = get_sim_imsi(modem_id)
    sim_key = sim_imsi or f"{operator.get('mcc', '')}{operator.get('mnc', '')}".strip()
    if remember and sim_key:
        LTE_SIM_OVERRIDES[sim_key] = {
            "id": profile_id or "custom",
            "apn": apn,
            "ipv4_method": ipv4_method,
            "ipv6_method": ipv6_method,
        }
        save_runtime_config()
    elif sim_key and sim_key in LTE_SIM_OVERRIDES and not remember:
        del LTE_SIM_OVERRIDES[sim_key]
        save_runtime_config()

    run_nmcli_full(["connection", "down", conn])
    code, stdout, stderr = run_nmcli_full(["connection", "up", conn])
    if code != 0:
        raise HTTPException(status_code=500, detail={"code": code, "stdout": stdout, "stderr": stderr})

    return {
        "ok": True,
        "connection": conn,
        "apn": apn,
        "ipv4_method": ipv4_method,
        "ipv6_method": ipv6_method,
        "remembered": bool(remember and sim_key),
    }

@app.get("/api/services")
def services():
    process_services = [
        {"name": "NetworkManager", "type": "host", "active": is_process_running("NetworkManager")},
        {"name": "ModemManager", "type": "host", "active": is_process_running("ModemManager")},
        {"name": "tailscaled", "type": "host", "active": is_process_running("tailscaled")},
        {"name": "smbd", "type": "host", "active": is_process_running("smbd")},
    ]

    discovered = parse_service_listeners()
    combined: dict[str, dict[str, object]] = {
        service["name"]: service for service in process_services if service["active"]
    }
    for service in discovered:
        combined[service["name"]] = service

    return sorted(combined.values(), key=lambda item: item["name"])


@app.get("/api/pihole/status")
def pihole_status():
    return get_pihole_status()


@app.get("/api/netalert/status")
def netalert_status():
    return get_netalert_status()


@app.get("/api/samba/status")
def samba_status():
    return get_samba_status()


@app.post("/api/samba/control")
def samba_control(payload: dict = Body(...)):
    action = str(payload.get("action", "")).strip().lower()
    if action not in {"start", "stop", "restart"}:
        raise HTTPException(status_code=400, detail="Invalid action")
    if command_exists("systemctl"):
        code, stdout, stderr = run_command_full(["systemctl", action, "smbd"])
    elif command_exists("service"):
        code, stdout, stderr = run_command_full(["service", "smbd", action])
    else:
        raise HTTPException(status_code=500, detail="No service manager available")
    if code != 0:
        raise HTTPException(status_code=500, detail={"code": code, "stdout": stdout, "stderr": stderr})
    return {"ok": True}


@app.post("/api/samba/user/password")
def samba_user_password(payload: dict = Body(...)):
    username = str(payload.get("username", "")).strip()
    password = str(payload.get("password", "")).strip()
    if not username or not password:
        raise HTTPException(status_code=400, detail="Username and password required")
    if not host_command_available("/usr/bin/smbpasswd"):
        raise HTTPException(status_code=500, detail="Host smbpasswd not available")
    code, stdout, stderr = run_command_input(host_binary_command("/usr/bin/smbpasswd", ["-L", "-a", "-s", username]), f"{password}\n{password}\n")
    if code != 0:
        raise HTTPException(status_code=500, detail={"code": code, "stdout": stdout, "stderr": stderr})
    return {"ok": True}


@app.post("/api/samba/user/delete")
def samba_user_delete(payload: dict = Body(...)):
    username = str(payload.get("username", "")).strip()
    if not username:
        raise HTTPException(status_code=400, detail="Username required")
    if not host_command_available("/usr/bin/smbpasswd"):
        raise HTTPException(status_code=500, detail="Host smbpasswd not available")
    code, stdout, stderr = run_command_full(host_binary_command("/usr/bin/smbpasswd", ["-L", "-x", username]))
    if code != 0:
        raise HTTPException(status_code=500, detail={"code": code, "stdout": stdout, "stderr": stderr})
    return {"ok": True, "username": username}


@app.post("/api/samba/user/state")
def samba_user_state(payload: dict = Body(...)):
    username = str(payload.get("username", "")).strip()
    action = str(payload.get("action", "")).strip().lower()
    if not username or action not in {"enable", "disable"}:
        raise HTTPException(status_code=400, detail="Username and valid action required")
    if not host_command_available("/usr/bin/smbpasswd"):
        raise HTTPException(status_code=500, detail="Host smbpasswd not available")
    flag = "-e" if action == "enable" else "-d"
    code, stdout, stderr = run_command_full(host_binary_command("/usr/bin/smbpasswd", ["-L", flag, username]))
    if code != 0:
        raise HTTPException(status_code=500, detail={"code": code, "stdout": stdout, "stderr": stderr})
    return {"ok": True, "username": username, "action": action}


@app.post("/api/samba/share")
def samba_share_save(payload: dict = Body(...)):
    name = str(payload.get("name", "")).strip()
    path = str(payload.get("path", "")).strip()
    read_only = str(payload.get("read_only", "No")).strip() or "No"
    guest_ok = str(payload.get("guest_ok", "No")).strip() or "No"
    valid_users = str(payload.get("valid_users", "")).strip()
    if not name or not path:
        raise HTTPException(status_code=400, detail="Share name and path are required")
    if not re.fullmatch(r"[A-Za-z0-9._-]+", name):
        raise HTTPException(status_code=400, detail="Share name may only contain letters, numbers, dot, dash, and underscore")

    ensure_samba_portal_include()
    shares = read_portal_samba_shares()
    updated = False
    for share in shares:
        if share["name"].lower() == name.lower():
            share.update({"name": name, "path": path, "read_only": read_only, "guest_ok": guest_ok, "valid_users": valid_users, "source": "portal"})
            updated = True
            break
    if not updated:
        shares.append({"name": name, "path": path, "read_only": read_only, "guest_ok": guest_ok, "valid_users": valid_users, "source": "portal"})
    write_portal_samba_shares(shares)
    test_samba_config()
    return {"ok": True, "share": name}


@app.post("/api/samba/share/delete")
def samba_share_delete(payload: dict = Body(...)):
    name = str(payload.get("name", "")).strip()
    if not name:
        raise HTTPException(status_code=400, detail="Share name is required")
    shares = [share for share in read_portal_samba_shares() if share["name"].lower() != name.lower()]
    write_portal_samba_shares(shares)
    test_samba_config()
    return {"ok": True, "share": name}


@app.get("/api/printing/status")
def printing_status():
    return get_printing_status()


@app.post("/api/printing/control")
def printing_control(payload: dict = Body(...)):
    action = str(payload.get("action", "")).strip().lower()
    if action not in {"start", "stop", "restart"}:
        raise HTTPException(status_code=400, detail="Invalid action")
    if not host_command_available("/usr/bin/systemctl"):
        raise HTTPException(status_code=500, detail="Host systemctl not available")
    status = get_printing_status()
    if not status.get("cups_installed"):
        raise HTTPException(status_code=500, detail="CUPS is not installed on the device")
    code, stdout, stderr = run_command_full(host_binary_command("/usr/bin/systemctl", [action, "cups"]))
    if code != 0:
        raise HTTPException(status_code=500, detail={"code": code, "stdout": stdout, "stderr": stderr})
    return {"ok": True, "action": action}


@app.get("/api/service-lan/clients")
def service_lan_clients():
    return get_all_lan_clients()


@app.get("/api/wifi/clients")
def wifi_clients():
    return get_wifi_clients()


@app.get("/api/service-lan/status")
def service_lan_status():
    ruleset = run_command(["nft", "list", "ruleset"])
    interface = get_service_lan_interface(ruleset)
    target = get_interface_data(interface)
    target.update(get_nmcli_device_status(interface))
    filter_enabled = has_nft_table(ruleset, "inet", "service_lan")
    ipv4_enabled = has_nft_table(ruleset, "ip", "service_lan_nat_v4")
    ipv6_enabled = has_nft_table(ruleset, "ip6", "service_lan_nat_v6")
    legacy_ipv4_enabled = has_nft_table(ruleset, "ip", "service_lan_nat")
    block_enabled = has_nft_table(ruleset, "inet", "service_lan_block")
    ipv4_active = ipv4_enabled or legacy_ipv4_enabled
    connection_mode = get_service_lan_connection_mode()
    dhcp_active = dhcp_listener_active()
    ra_active = ipv6_ra_active()
    forwarding_v4 = forwarding_active(4)
    forwarding_v6 = forwarding_active(6)
    default_v4 = has_default_route(4)
    default_v6 = has_default_route(6)
    interface_v6_disabled = interface_ipv6_disabled(interface)
    interface_conflict = same_physical_lan_interface(get_main_lan_interface(), interface)
    ipv4_path_ready = (
        service_lan_cfg("enable_ipv4") == "true"
        and forwarding_v4
        and default_v4
        and (filter_enabled or ipv4_active or connection_mode == "shared")
    )
    ipv6_path_ready = (
        service_lan_cfg("enable_ipv6") == "true"
        and filter_enabled
        and ipv6_enabled
        and forwarding_v6
        and default_v6
        and ra_active
        and not interface_v6_disabled
    )
    internet_enabled = not block_enabled and (ipv4_path_ready or ipv6_path_ready)

    return {
        "name": service_lan_cfg("name") or "Service LAN",
        "role": service_lan_cfg("role"),
        "interface": interface,
        "target_interface": interface,
        "target_interface_status": target,
        "available_interfaces": [iface["name"] for iface in ethernet_candidates()],
        "role_description": role_description(service_lan_cfg("role")),
        "connection_mode_ipv4": connection_mode,
        "ipv4_mode": "shared" if service_lan_cfg("enable_ipv4") == "true" else "disabled",
        "ipv4_enabled": service_lan_cfg("enable_ipv4") == "true",
        "ipv6_enabled": service_lan_cfg("enable_ipv6") == "true",
        "gateway_ipv4": service_lan_cfg("ipv4_gateway") if service_lan_cfg("enable_ipv4") == "true" else "",
        "ipv4_subnet": service_lan_cfg("ipv4_subnet") if service_lan_cfg("enable_ipv4") == "true" else "",
        "dhcp_range_ipv4": service_lan_cfg("dhcp_range") if service_lan_cfg("enable_ipv4") == "true" else "",
        "dhcp_listener_active": dhcp_active,
        "ipv6_mode": "routed" if service_lan_cfg("enable_ipv6") == "true" else "disabled",
        "gateway_ipv6": service_lan_cfg("ipv6_gateway") if service_lan_cfg("enable_ipv6") == "true" else "",
        "prefix_ipv6": service_lan_cfg("ipv6_prefix") if service_lan_cfg("enable_ipv6") == "true" else "",
        "dns_servers": [item.strip() for item in service_lan_cfg("dns_servers").split(",") if item.strip()],
        "dns_search": service_lan_cfg("dns_search"),
        "interface_ipv6_disabled": interface_v6_disabled,
        "forwarding_ipv4_active": forwarding_v4,
        "forwarding_ipv6_active": forwarding_v6,
        "upstream_ipv4_default_route": default_v4,
        "upstream_ipv6_default_route": default_v6,
        "router_advertisements_active": ra_active,
        "firewall_ipv4_active": ipv4_active,
        "firewall_ipv6_active": ipv6_enabled,
        "firewall_filter_active": filter_enabled,
        "firewall_block_active": block_enabled,
        "ipv4_path_ready": ipv4_path_ready,
        "ipv6_path_ready": ipv6_path_ready,
        "internet_enabled": internet_enabled,
        "interface_conflict": interface_conflict,
        "notes": [
            role_description(service_lan_cfg("role")),
            "shared = DHCP + NAT for IPv4 clients on the service port",
            "routed = IPv6 forwarding and router advertisements for service clients",
            "plugging in a USB Ethernet adapter gives the portal another port it can auto-assign",
        ] + (["choose a different physical interface from Main LAN to keep Service LAN isolated"] if interface_conflict else []),
    }


@app.get("/api/main-lan/status")
@app.get("/api/lan/profile")
def lan_profile():
    target_interface = get_main_lan_interface()
    target = get_interface_data(target_interface)
    target.update(get_nmcli_device_status(target_interface))
    ruleset = run_command(["nft", "list", "ruleset"])
    blocked = interface_block_active(ruleset, target_interface)
    interface_conflict = same_physical_lan_interface(target_interface, get_service_lan_interface())
    connection = get_nmcli_connection_status("main-lan")

    return {
        "name": "Main LAN",
        "role": normalize_lan_role(lan_cfg("role")),
        "target_interface": target_interface,
        "target_interface_status": target,
        "available_interfaces": [iface["name"] for iface in ethernet_candidates()],
        "role_description": role_description(lan_cfg("role")),
        "internet_enabled": not blocked,
        "blocked_by_portal": blocked,
        "interface_conflict": interface_conflict,
        "ipv4_mode": lan_cfg("ipv4_mode"),
        "ipv4_address": lan_cfg("ipv4_address"),
        "ipv4_subnet": lan_cfg("ipv4_subnet"),
        "dhcp_range": lan_cfg("dhcp_range"),
        "ipv6_mode": lan_cfg("ipv6_mode"),
        "ipv6_address": lan_cfg("ipv6_address"),
        "ipv6_prefix": lan_cfg("ipv6_prefix"),
        "dns_servers": [item.strip() for item in lan_cfg("dns_servers").split(",") if item.strip()],
        "dns_search": lan_cfg("dns_search"),
        "nmcli_available": nmcli_available(),
        "connection": connection,
        "notes": [
            role_description(lan_cfg("role")),
            "shared = DHCP + NAT for local clients",
            "manual = static LAN without DHCP/NAT automation",
            "plugging in a USB Ethernet adapter gives the portal another port it can auto-assign",
        ] + (["choose a different physical interface from Service LAN to keep Main LAN separate"] if interface_conflict else []),
    }


@app.post("/api/main-lan/apply")
def main_lan_apply():
    code, stdout, stderr = configure_main_lan()
    if code != 0:
        raise HTTPException(
            status_code=500,
            detail={"code": code, "stdout": stdout, "stderr": stderr or "Main LAN apply failed"},
        )
    return {"ok": True, "code": code, "stdout": stdout, "stderr": stderr}


@app.post("/api/main-lan/restart")
def main_lan_restart():
    nmcli_cmd = host_nmcli_command if host_nmcli_available() else (lambda args: ["nmcli"] + args)
    if not host_nmcli_available() and not command_exists("nmcli"):
        raise HTTPException(status_code=500, detail="nmcli is not available")
    code, stdout, stderr = run_command_full(nmcli_cmd(["connection", "down", "main-lan"]))
    code2, stdout2, stderr2 = run_command_full(nmcli_cmd(["connection", "up", "main-lan"]))
    if code2 != 0:
        raise HTTPException(
            status_code=500,
            detail={"code": code2, "stdout": "\n".join([stdout, stdout2]).strip(), "stderr": "\n".join([stderr, stderr2]).strip()},
        )
    return {"ok": True, "stdout": "\n".join([stdout, stdout2]).strip(), "stderr": "\n".join([stderr, stderr2]).strip()}


def service_lan_command_env() -> dict[str, str]:
    return {
        "SERVICE_LAN_INTERFACE": get_service_lan_interface(),
        "SERVICE_LAN_IPV4_GATEWAY": service_lan_cfg("ipv4_gateway"),
        "SERVICE_LAN_IPV4_SUBNET": service_lan_cfg("ipv4_subnet"),
        "SERVICE_LAN_DHCP_RANGE": service_lan_cfg("dhcp_range"),
        "SERVICE_LAN_IPV6_GATEWAY": service_lan_cfg("ipv6_gateway"),
        "SERVICE_LAN_IPV6_PREFIX": service_lan_cfg("ipv6_prefix"),
        "SERVICE_LAN_ENABLE_IPV4": service_lan_cfg("enable_ipv4"),
        "SERVICE_LAN_ENABLE_IPV6": service_lan_cfg("enable_ipv6"),
    }


@app.post("/api/service-lan/apply")
def service_lan_apply():
    env = service_lan_command_env()
    stdout_parts = []
    stderr_parts = []
    run_command_full(
        ["/usr/local/bin/service-lan-inet-off.sh"],
        env={
            "SERVICE_LAN_INTERFACE": env["SERVICE_LAN_INTERFACE"],
            "SERVICE_LAN_IPV6_GATEWAY": env["SERVICE_LAN_IPV6_GATEWAY"],
            "SERVICE_LAN_IPV6_PREFIX": env["SERVICE_LAN_IPV6_PREFIX"],
        },
    )
    code, stdout, stderr = run_command_full(["/usr/local/bin/service-lan-inet-on.sh"], env=env)
    if stdout:
        stdout_parts.append(stdout)
    if stderr:
        stderr_parts.append(stderr)
    if code != 0:
        raise HTTPException(
            status_code=500,
            detail={"code": code, "stdout": "\n".join(stdout_parts).strip(), "stderr": "\n".join(stderr_parts).strip() or "Service LAN apply failed"},
        )
    return {"ok": True, "stdout": "\n".join(stdout_parts).strip(), "stderr": "\n".join(stderr_parts).strip()}


@app.post("/api/service-lan/restart")
def service_lan_restart():
    interface = get_service_lan_interface()
    stdout_parts = []
    stderr_parts = []
    for cmd in (["ip", "link", "set", "dev", interface, "down"], ["ip", "link", "set", "dev", interface, "up"]):
        code, stdout, stderr = run_command_full(cmd)
        if stdout:
            stdout_parts.append(stdout)
        if stderr:
            stderr_parts.append(stderr)
        if code != 0:
            raise HTTPException(status_code=500, detail={"code": code, "stdout": "\n".join(stdout_parts).strip(), "stderr": "\n".join(stderr_parts).strip()})
    return {"ok": True, "stdout": "\n".join(stdout_parts).strip(), "stderr": "\n".join(stderr_parts).strip()}


@app.post("/api/main-lan/internet/on")
def main_lan_internet_on():
    code, stdout, stderr = set_interface_block(get_main_lan_interface(), False)
    if code != 0:
        raise HTTPException(
            status_code=500,
            detail={"code": code, "stdout": stdout, "stderr": stderr or "Main LAN internet enable failed"},
        )
    return {"ok": True, "code": code, "stdout": stdout, "stderr": stderr}


@app.post("/api/main-lan/internet/off")
def main_lan_internet_off():
    code, stdout, stderr = set_interface_block(get_main_lan_interface(), True)
    if code != 0:
        raise HTTPException(
            status_code=500,
            detail={"code": code, "stdout": stdout, "stderr": stderr or "Main LAN internet disable failed"},
        )
    return {"ok": True, "code": code, "stdout": stdout, "stderr": stderr}


@app.post("/api/interfaces/{interface}/link/up")
def interface_link_up(interface: str):
    code, stdout, stderr = run_command_full(["ip", "link", "set", "dev", interface, "up"])
    if code != 0:
        raise HTTPException(
            status_code=500,
            detail={"code": code, "stdout": stdout, "stderr": stderr or f"Failed to bring {interface} up"},
        )
    return {"ok": True, "code": code, "stdout": stdout, "stderr": stderr}


@app.post("/api/interfaces/{interface}/link/down")
def interface_link_down(interface: str):
    code, stdout, stderr = run_command_full(["ip", "link", "set", "dev", interface, "down"])
    if code != 0:
        raise HTTPException(
            status_code=500,
            detail={"code": code, "stdout": stdout, "stderr": stderr or f"Failed to bring {interface} down"},
        )
    return {"ok": True, "code": code, "stdout": stdout, "stderr": stderr}


@app.post("/api/main-lan/config")
def update_main_lan_config(payload: dict = Body(...)):
    proposed_target = str(payload.get("target_interface", lan_cfg("target_interface"))).strip()
    if proposed_target and same_physical_lan_interface(proposed_target, get_service_lan_interface()):
        raise HTTPException(status_code=400, detail="Main LAN and Service LAN cannot use the same interface")
    allowed = {
        "target_interface",
        "role",
        "ipv4_mode",
        "ipv4_address",
        "ipv4_subnet",
        "dhcp_range",
        "ipv6_mode",
        "ipv6_address",
        "ipv6_prefix",
        "dns_servers",
        "dns_search",
    }
    for key, value in payload.items():
        if key in allowed and isinstance(value, str):
            MAIN_LAN_CONFIG[key] = normalize_lan_role(value) if key == "role" else value.strip()
    save_runtime_config()
    return {"ok": True, "config": MAIN_LAN_CONFIG}


@app.get("/api/active-sessions")
def active_sessions():
    return get_active_sessions()


@app.post("/api/service-lan/config")
def update_service_lan_config(payload: dict = Body(...)):
    proposed_interface = str(payload.get("interface", service_lan_cfg("interface"))).strip()
    if proposed_interface and same_physical_lan_interface(get_main_lan_interface(), proposed_interface):
        raise HTTPException(status_code=400, detail="Service LAN and Main LAN cannot use the same interface")
    allowed = {
        "interface",
        "role",
        "ipv4_mode",
        "ipv4_gateway",
        "ipv4_subnet",
        "dhcp_range",
        "ipv6_mode",
        "ipv6_gateway",
        "ipv6_prefix",
        "enable_ipv4",
        "enable_ipv6",
        "dns_servers",
        "dns_search",
    }
    for key, value in payload.items():
        if key in allowed and isinstance(value, str):
            SERVICE_LAN_CONFIG[key] = normalize_lan_role(value) if key == "role" else value.strip()
    if "ipv4_mode" in payload and isinstance(payload.get("ipv4_mode"), str):
        SERVICE_LAN_CONFIG["enable_ipv4"] = "true" if payload["ipv4_mode"].strip() != "disabled" else "false"
    if "ipv6_mode" in payload and isinstance(payload.get("ipv6_mode"), str):
        SERVICE_LAN_CONFIG["enable_ipv6"] = "true" if payload["ipv6_mode"].strip() != "disabled" else "false"
    save_runtime_config()
    return {"ok": True, "config": SERVICE_LAN_CONFIG}


@app.get("/api/wifi/status")
def wifi_status():
    return get_wifi_status()


@app.post("/api/wifi/config")
def update_wifi_config(payload: dict = Body(...)):
    allowed = {
        "interface",
        "mode",
        "ssid",
        "password",
        "hotspot_ssid",
        "hotspot_password",
        "hotspot_security",
        "ipv4_method",
        "ipv4_address",
        "ipv6_method",
        "ipv6_address",
    }
    for key, value in payload.items():
        if key in allowed and isinstance(value, str):
            WIFI_CONFIG[key] = value.strip()
    save_runtime_config()
    public_wifi_config = dict(WIFI_CONFIG)
    for key in WIFI_SECRET_KEYS:
        public_wifi_config[key] = ""
    return {"ok": True, "config": public_wifi_config}


@app.post("/api/wifi/scan")
def wifi_scan():
    interface = wifi_cfg("interface")
    return {"ok": True, "interface": interface, "scan": get_wifi_scan(interface, force_rescan=True)}


@app.post("/api/wifi/power/{state}")
def wifi_power(state: str):
    if state not in {"on", "off"}:
        raise HTTPException(status_code=400, detail="invalid power state")
    code, stdout, stderr = set_wifi_power(state)
    if code != 0:
        raise HTTPException(
            status_code=500,
            detail={"code": code, "stdout": stdout, "stderr": stderr or f"Wi-Fi power {state} failed"},
        )
    return {"ok": True, "state": state, "stdout": stdout, "stderr": stderr}


@app.post("/api/wifi/apply")
def wifi_apply():
    code, stdout, stderr = apply_wifi_mode()
    if code != 0:
        raise HTTPException(
            status_code=500,
            detail={"code": code, "stdout": stdout, "stderr": stderr or "Wi-Fi apply failed"},
        )
    return {"ok": True, "code": code, "stdout": stdout, "stderr": stderr}



@app.post("/api/service-lan/internet/on")
def service_lan_internet_on():
    env = service_lan_command_env()
    code, stdout, stderr = run_command_full(["/usr/local/bin/service-lan-inet-on.sh"], env=env)
    if code != 0:
        raise HTTPException(
            status_code=500,
            detail={"code": code, "stdout": stdout, "stderr": stderr or "Service LAN enable failed"},
        )
    return {"ok": True, "code": code, "stdout": stdout, "stderr": stderr}


@app.post("/api/service-lan/internet/off")
def service_lan_internet_off():
    code, stdout, stderr = run_command_full(
        ["/usr/local/bin/service-lan-inet-off.sh"],
        env={
            "SERVICE_LAN_INTERFACE": get_service_lan_interface(),
            "SERVICE_LAN_IPV6_GATEWAY": service_lan_cfg("ipv6_gateway"),
            "SERVICE_LAN_IPV6_PREFIX": service_lan_cfg("ipv6_prefix"),
        },
    )
    if code != 0:
        raise HTTPException(
            status_code=500,
            detail={"code": code, "stdout": stdout, "stderr": stderr or "Service LAN disable failed"},
        )
    return {"ok": True, "code": code, "stdout": stdout, "stderr": stderr}


@app.post("/api/system/restart")
def system_restart():
    if host_command_available("/usr/sbin/shutdown"):
        cmd = ["chroot", "/host", "/usr/sbin/shutdown", "-r", "now"]
    elif host_command_available("/usr/sbin/reboot"):
        cmd = ["chroot", "/host", "/usr/sbin/reboot"]
    else:
        raise HTTPException(status_code=500, detail="Host restart command not available")
    code, stdout, stderr = run_command_full(cmd)
    if code != 0:
        raise HTTPException(status_code=500, detail={"code": code, "stdout": stdout, "stderr": stderr or "Restart command failed"})
    return {"ok": True, "stdout": stdout, "stderr": stderr}


@app.post("/api/system/poweroff")
def system_poweroff():
    if host_command_available("/usr/sbin/shutdown"):
        cmd = ["chroot", "/host", "/usr/sbin/shutdown", "-P", "now"]
    elif host_command_available("/usr/sbin/poweroff"):
        cmd = ["chroot", "/host", "/usr/sbin/poweroff"]
    else:
        raise HTTPException(status_code=500, detail="Host poweroff command not available")
    code, stdout, stderr = run_command_full(cmd)
    if code != 0:
        raise HTTPException(status_code=500, detail={"code": code, "stdout": stdout, "stderr": stderr or "Power off command failed"})
    return {"ok": True, "stdout": stdout, "stderr": stderr}


@app.get("/", response_class=HTMLResponse)
def home():
    return HTMLResponse(Path(__file__).with_name("portal.html").read_text())
    return """
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="utf-8" />
      <meta name="viewport" content="width=device-width, initial-scale=1" />
      <title>R1000 Network Panel</title>
      <style>
        body {
          font-family: "Segoe UI", "Helvetica Neue", sans-serif;
          background:
            radial-gradient(circle at top, rgba(59, 130, 246, 0.22), transparent 28%),
            linear-gradient(180deg, #07111f 0%, #0f172a 46%, #121826 100%);
          color: #e5e7eb;
          margin: 0;
          min-height: 100vh;
          padding: 16px;
        }
        h1, h2 { margin-top: 0; }
        h2 {
          font-size: 18px;
          margin-bottom: 12px;
        }
        .topbar {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 12px;
        }
        .grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
          gap: 12px;
        }
        .card {
          background: rgba(15, 23, 42, 0.88);
          border: 1px solid rgba(148, 163, 184, 0.18);
          border-radius: 18px;
          padding: 14px;
          box-shadow: 0 12px 28px rgba(2, 6, 23, 0.28);
          backdrop-filter: blur(12px);
          overflow-wrap: anywhere;
          word-break: break-word;
        }
        details.menu {
          border: 1px solid rgba(148, 163, 184, 0.16);
          border-radius: 12px;
          padding: 6px 8px;
          background: rgba(8, 15, 29, 0.6);
        }
        details.menu > summary {
          list-style: none;
          cursor: pointer;
          font-weight: 700;
          font-size: 12px;
          color: #e2e8f0;
        }
        details.menu > summary::-webkit-details-marker {
          display: none;
        }
        .menu-content {
          margin-top: 8px;
        }
        .dense {
          display: grid;
          gap: 8px;
        }
        .metric {
          padding: 8px 10px;
          border-radius: 12px;
          background: rgba(15, 23, 42, 0.55);
          border: 1px solid rgba(148, 163, 184, 0.1);
        }
        .label {
          color: #94a3b8;
          font-size: 12px;
        }
        .value {
          font-size: 16px;
          font-weight: 700;
          margin-top: 4px;
        }
        ul {
          padding-left: 18px;
          margin: 0;
        }
        li {
          margin-bottom: 6px;
          line-height: 1.35;
        }
        .route {
          background: rgba(8, 15, 29, 0.72);
          border: 1px solid rgba(148, 163, 184, 0.14);
          border-radius: 12px;
          padding: 8px 10px;
          margin-top: 8px;
          font-family: monospace;
          font-size: 12px;
          line-height: 1.4;
          white-space: pre-wrap;
          word-break: break-word;
          overflow-wrap: anywhere;
        }
        button {
          background: linear-gradient(135deg, #0ea5e9, #2563eb);
          color: white;
          border: none;
          border-radius: 10px;
          padding: 8px 11px;
          font-weight: 700;
          font-size: 12px;
          cursor: pointer;
        }
        button:hover {
          filter: brightness(1.08);
        }
        button.secondary {
          background: rgba(30, 41, 59, 0.88);
          border: 1px solid rgba(148, 163, 184, 0.18);
        }
        .pill {
          display: inline-flex;
          align-items: center;
          border-radius: 999px;
          padding: 3px 8px;
          font-size: 11px;
          font-weight: 700;
          margin-top: 6px;
          background: rgba(14, 165, 233, 0.14);
          color: #7dd3fc;
        }
        .chip {
          display: inline-flex;
          align-items: center;
          gap: 6px;
          border-radius: 999px;
          padding: 2px 8px;
          font-size: 11px;
          font-weight: 700;
          background: rgba(15, 23, 42, 0.7);
          border: 1px solid rgba(148, 163, 184, 0.18);
          color: #cbd5f5;
        }
        .controls {
          display: flex;
          gap: 8px;
          flex-wrap: wrap;
          margin-top: 10px;
        }
        .compact-grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
          gap: 8px;
        }
        .hint {
          color: #7c8aa5;
          font-size: 11px;
          margin-top: 8px;
        }
        input, select {
          width: 100%;
          box-sizing: border-box;
          background: rgba(8, 15, 29, 0.92);
          color: #e5e7eb;
          border: 1px solid rgba(148, 163, 184, 0.18);
          border-radius: 10px;
          padding: 8px 10px;
          font-size: 12px;
          margin-top: 4px;
        }
        select.compact {
          padding: 6px 8px;
        }
        a.service-link {
          color: #7dd3fc;
          text-decoration: none;
          font-weight: 700;
        }
        a.service-link:hover {
          text-decoration: underline;
        }
      </style>
    </head>
    <body>
      <div class="topbar">
        <h1>R1000 Network Panel</h1>
        <button onclick="render()">Refresh</button>
      </div>

      <div class="grid">
        <div class="card">
          <h2>Overview</h2>
          <div id="overview">Loading...</div>
        </div>
        <div class="card">
          <h2>LTE</h2>
          <div id="lte">Loading...</div>
        </div>
        <div class="card">
          <h2>LTE APN</h2>
          <div id="lte-apn">Loading...</div>
        </div>
        <div class="card">
          <h2>Services</h2>
          <div id="services">Loading...</div>
        </div>
        <div class="card">
          <h2>Samba</h2>
          <div id="samba-panel">Loading...</div>
        </div>
        <div class="card">
          <h2>Service LAN</h2>
          <div id="service-lan">Loading...</div>
        </div>
        <div class="card">
          <h2>Main LAN</h2>
          <div id="main-lan">Loading...</div>
        </div>
        <div class="card">
          <h2>Wi-Fi</h2>
          <div id="wifi-panel">Loading...</div>
        </div>
      </div>

      <div class="card" style="margin-top:16px;">
        <h2>Interfaces</h2>
        <div id="interfaces">Loading...</div>
      </div>

      <div class="card" style="margin-top:16px;">
        <h2>Connected Clients</h2>
        <div id="service-lan-clients">Loading...</div>
      </div>

      <div class="card" style="margin-top:16px;">
        <h2>Active Sessions</h2>
        <div id="active-sessions">Loading...</div>
      </div>

      <script>
        const appState = {
          drafts: {},
        };

        async function loadJSON(url) {
          const res = await fetch(url);
          return await res.json();
        }

        function draftValue(key, fallback) {
          return Object.prototype.hasOwnProperty.call(appState.drafts, key)
            ? appState.drafts[key]
            : (fallback ?? '');
        }

        function bindDraft(id, key) {
          const el = document.getElementById(id);
          if (!el) return;
          el.oninput = () => {
            appState.drafts[key] = el.type === 'checkbox' ? (el.checked ? 'true' : 'false') : el.value;
          };
          el.onchange = el.oninput;
        }

        function clearDraft(prefix) {
          Object.keys(appState.drafts)
            .filter(key => key.startsWith(prefix))
            .forEach(key => delete appState.drafts[key]);
        }

        async function toggleServiceLanInternet(mode) {
          const endpoint = mode === 'on'
            ? '/api/service-lan/internet/on'
            : '/api/service-lan/internet/off';
          await postAction(endpoint, 'Failed to change Service LAN internet state');
          await render();
        }

        async function postAction(endpoint, fallbackMessage) {
          const res = await fetch(endpoint, { method: 'POST' });
          if (!res.ok) {
            let message = fallbackMessage;
            try {
              const payload = await res.json();
              const detail = payload.detail || payload;
              if (typeof detail === 'string') {
                message = detail;
              } else if (detail && detail.stderr) {
                message = detail.stderr;
              }
            } catch (err) {
            }
            alert(message);
            return false;
          }

          const payload = await res.json();
          if (!payload.ok) {
            alert(payload.stderr || fallbackMessage);
            return false;
          }

          return true;
        }

        async function applyMainLan() {
          const ok = await postAction('/api/main-lan/apply', 'Failed to apply Main LAN profile');
          if (ok) await render();
        }

        async function saveMainLanConfig() {
          const payload = {
            target_interface: document.getElementById('main-lan-target-interface').value,
            role: document.getElementById('main-lan-role').value,
            ipv4_mode: document.getElementById('main-lan-ipv4-mode').value,
            ipv4_address: document.getElementById('main-lan-ipv4-address').value,
            ipv4_subnet: document.getElementById('main-lan-ipv4-subnet').value,
            dhcp_range: document.getElementById('main-lan-dhcp-range').value,
            ipv6_mode: document.getElementById('main-lan-ipv6-mode').value,
            ipv6_address: document.getElementById('main-lan-ipv6-address').value,
            ipv6_prefix: document.getElementById('main-lan-ipv6-prefix').value,
            dns_servers: document.getElementById('main-lan-dns-servers').value,
            dns_search: document.getElementById('main-lan-dns-search').value,
          };
          const res = await fetch('/api/main-lan/config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
          });
          if (!res.ok) {
            alert('Failed to save Main LAN configuration');
            return;
          }
          clearDraft('main_lan.');
          await render();
        }

        async function saveServiceLanConfig() {
          const payload = {
            interface: document.getElementById('service-lan-interface').value,
            ipv4_gateway: document.getElementById('service-lan-ipv4-gateway').value,
            ipv4_subnet: document.getElementById('service-lan-ipv4-subnet').value,
            dhcp_range: document.getElementById('service-lan-dhcp-range').value,
            ipv6_gateway: document.getElementById('service-lan-ipv6-gateway').value,
            ipv6_prefix: document.getElementById('service-lan-ipv6-prefix').value,
            enable_ipv4: document.getElementById('service-lan-enable-ipv4').value,
            enable_ipv6: document.getElementById('service-lan-enable-ipv6').value,
          };
          const res = await fetch('/api/service-lan/config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
          });
          if (!res.ok) {
            alert('Failed to save Service LAN configuration');
            return;
          }
          clearDraft('service_lan.');
          await render();
        }

        async function saveWifiConfig() {
          const payload = {
            interface: document.getElementById('wifi-interface').value,
            mode: document.getElementById('wifi-mode').value,
            ssid: document.getElementById('wifi-ssid').value,
            password: document.getElementById('wifi-password').value,
            hotspot_ssid: document.getElementById('wifi-hotspot-ssid').value,
            hotspot_password: document.getElementById('wifi-hotspot-password').value,
            ipv4_method: document.getElementById('wifi-ipv4-method').value,
            ipv4_address: document.getElementById('wifi-ipv4-address').value,
            ipv6_method: document.getElementById('wifi-ipv6-method').value,
            ipv6_address: document.getElementById('wifi-ipv6-address').value,
          };
          const res = await fetch('/api/wifi/config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
          });
          if (!res.ok) {
            alert('Failed to save Wi-Fi configuration');
            return;
          }
          clearDraft('wifi.');
          await render();
        }

        async function applyWifi() {
          const ok = await postAction('/api/wifi/apply', 'Failed to apply Wi-Fi configuration');
          if (ok) await render();
        }

        async function restartMainLan() {
          const ok = await postAction('/api/main-lan/restart', 'Failed to restart Main LAN connection');
          if (ok) await render();
        }

        async function toggleMainLanInternet(mode) {
          const endpoint = mode === 'on'
            ? '/api/main-lan/internet/on'
            : '/api/main-lan/internet/off';
          const ok = await postAction(endpoint, 'Failed to change Main LAN internet state');
          if (ok) await render();
        }

        async function applyLteApn() {
          const payload = {
            profile_id: document.getElementById('lte-apn-profile').value,
            apn: document.getElementById('lte-apn-custom').value,
            ipv4_method: document.getElementById('lte-ipv4-method').value,
            ipv6_method: document.getElementById('lte-ipv6-method').value,
            remember: document.getElementById('lte-apn-remember').value,
          };
          const res = await fetch('/api/lte/apn/apply', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
          });
          if (!res.ok) {
            alert('Failed to apply LTE APN settings');
            return;
          }
          await render();
        }

        async function applySuggestedApn(profileId) {
          if (!profileId) return;
          document.getElementById('lte-apn-profile').value = profileId;
          document.getElementById('lte-apn-custom').value = '';
          await applyLteApn();
        }

        async function toggleAutoApn(enabled) {
          const res = await fetch('/api/lte/apn/auto', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ enabled }),
          });
          if (!res.ok) {
            alert('Failed to update auto APN setting');
            return;
          }
          await render();
        }

        function updateApnFields() {
          const select = document.getElementById('lte-apn-profile');
          if (!select || !window.lteApnOptions) return;
          const id = select.value;
          const option = window.lteApnOptions.find(o => o.id === id);
          if (!option) return;
          document.getElementById('lte-apn-custom').value = option.apn;
          document.getElementById('lte-ipv4-method').value = option.ipv4_method;
          document.getElementById('lte-ipv6-method').value = option.ipv6_method;
          const details = document.getElementById('lte-apn-details');
          if (details) {
            details.innerText = `${option.provider} | APN: ${option.apn} | v4: ${option.ipv4_method} | v6: ${option.ipv6_method}`;
          }
        }

        async function controlSamba(action) {
          const res = await fetch('/api/samba/control', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action }),
          });
          if (!res.ok) {
            alert('Failed to control Samba');
            return;
          }
          await render();
        }

        async function setSambaPassword() {
          const payload = {
            username: document.getElementById('samba-username').value,
            password: document.getElementById('samba-password').value,
          };
          const res = await fetch('/api/samba/user/password', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
          });
          if (!res.ok) {
            alert('Failed to set Samba password');
            return;
          }
          alert('Samba password updated');
          await render();
        }

        async function setLinkState(name, state) {
          const endpoint = `/api/interfaces/${name}/link/${state}`;
          const ok = await postAction(endpoint, `Failed to set ${name} ${state}`);
          if (ok) await render();
        }

        function getServiceUrl(service) {
          const host = window.location.hostname;
          const currentProtocol = window.location.protocol === 'https:' ? 'https:' : 'http:';
          const ports = service.ports || [];
          const hasPort = (value) => ports.includes(value);

          if (service.name === 'Network Panel') {
            return window.location.origin;
          }
          if (service.name === 'Cockpit' || hasPort('tcp/9090')) {
            return `https://${host}:9090`;
          }
          if (service.name === 'Portainer HTTPS' || hasPort('tcp/9443')) {
            return `https://${host}:9443`;
          }
          if (service.name === 'Portainer' || hasPort('tcp/9000')) {
            return `http://${host}:9000`;
          }
          if (service.name === 'Grafana' || hasPort('tcp/3000')) {
            return `http://${host}:3000`;
          }
          if (service.name === 'Prometheus' || hasPort('tcp/9091')) {
            return `http://${host}:9091`;
          }
          if (service.name === 'Pi-hole' || hasPort('tcp/8081')) {
            return `http://${host}:8081`;
          }
          if (service.name === 'SSH' || hasPort('tcp/22')) {
            return `ssh://${host}`;
          }

          const tcpPort = ports.find(p => p.startsWith('tcp/'));
          if (!tcpPort) {
            return '';
          }

          const port = tcpPort.split('/')[1];
          return `${currentProtocol}//${host}:${port}`;
        }

        async function render() {
          const overview = await loadJSON('/api/overview');
          const lte = await loadJSON('/api/lte');
          const lteProfile = await loadJSON('/api/lte/profile');
          const lteOptions = await loadJSON('/api/lte/apn/options');
          const lteSuggest = await loadJSON('/api/lte/apn/suggest');
          const lteAuto = await loadJSON('/api/lte/apn/auto');
          const services = await loadJSON('/api/services');
          const samba = await loadJSON('/api/samba/status');
          const interfaces = await loadJSON('/api/interfaces');
          const serviceLan = await loadJSON('/api/service-lan/status');
          const serviceLanClients = await loadJSON('/api/service-lan/clients');
          const lanProfile = await loadJSON('/api/main-lan/status');
          const activeSessions = await loadJSON('/api/active-sessions');
          const wifi = await loadJSON('/api/wifi/status');

          document.getElementById('overview').innerHTML = `
            <div class="compact-grid">
              <div class="metric">
                <div class="label">Hostname</div>
                <div class="value">${overview.hostname}</div>
              </div>
              <div class="metric">
                <div class="label">Uptime (sec)</div>
                <div class="value">${overview.uptime_seconds}</div>
              </div>
            </div>
            <div class="pill">Uplink Summary</div>

            <div class="route">
              <div class="label">Primary IPv4 Uplink</div>
              <div>Interface: ${overview.uplink_ipv4.dev || '-'}</div>
              <div>Gateway: ${overview.uplink_ipv4.via || '-'}</div>
              <div>Source: ${overview.uplink_ipv4.src || '-'}</div>
            </div>

            <div class="route">
              <div class="label">Primary IPv6 Uplink</div>
              <div>Interface: ${overview.uplink_ipv6.dev || '-'}</div>
              <div>Gateway: ${overview.uplink_ipv6.via || '-'}</div>
              <div>Source: ${overview.uplink_ipv6.src || '-'}</div>
            </div>

            <div class="route">
              <div class="label">Detected Uplinks</div>
              <div>${(overview.uplinks || []).map(i => `${i.name} (${i.role}, ${i.state})`).join('<br>') || '-'}</div>
            </div>

            <div class="route">
              <div class="label">Local LAN Ports</div>
              <div>${(overview.local_lans || []).map(i => `${i.name} (${i.state}) IPv4: ${(i.ipv4 || []).join(', ') || '-'} IPv6: ${(i.ipv6 || []).join(', ') || '-'}`).join('<br>') || '-'}</div>
            </div>
          `;

          document.getElementById('lte').innerHTML = `
            <div class="compact-grid">
              <div class="metric"><div class="label">Available</div><div class="value">${lte.available}</div></div>
              <div class="metric"><div class="label">State</div><div class="value">${lte.state || '-'}</div></div>
              <div class="metric"><div class="label">Operator</div><div class="value">${lte.operator_name || '-'}</div></div>
              <div class="metric"><div class="label">Signal</div><div class="value">${lte.signal_quality || '-'}</div></div>
              <div class="metric"><div class="label">Tech</div><div class="value">${lte.access_tech || '-'}</div></div>
              <div class="metric"><div class="label">RSSI</div><div class="value">${lte.rssi || '-'}</div></div>
              <div class="metric"><div class="label">RSRP</div><div class="value">${lte.rsrp || '-'}</div></div>
              <div class="metric"><div class="label">RSRQ</div><div class="value">${lte.rsrq || '-'}</div></div>
              <div class="metric"><div class="label">SNR</div><div class="value">${lte.snr || '-'}</div></div>
            </div>
          `;

          const suggestedId = (lteSuggest.override && lteSuggest.override.id) ? lteSuggest.override.id : ((lteSuggest.suggested && lteSuggest.suggested.id) || '');
          window.lteApnOptions = lteOptions.options || [];
          document.getElementById('lte-apn').innerHTML = `
            <div class="compact-grid">
              <div class="metric"><div class="label">Connection</div><div class="value">${lteProfile.connection || '-'}</div></div>
              <div class="metric"><div class="label">Current APN</div><div class="value">${lteProfile.apn || '-'}</div></div>
              <div class="metric"><div class="label">IPv4 Method</div><div class="value">${lteProfile.ipv4_method || '-'}</div></div>
              <div class="metric"><div class="label">IPv6 Method</div><div class="value">${lteProfile.ipv6_method || '-'}</div></div>
              <div class="metric"><div class="label">Operator MCC/MNC</div><div class="value">${lte.operator_mcc || '-'}/${lte.operator_mnc || '-'}</div></div>
            </div>
            <details class="menu">
              <summary>Auto Apply</summary>
              <div class="menu-content compact-grid">
                <div class="metric">
                  <div class="label">Auto Apply APN</div>
                  <select class="compact" id="lte-auto-apn" onchange="toggleAutoApn(this.value === 'true')">
                    ${['true', 'false'].map(v => `<option value="${v}" ${(lteAuto.enabled ? 'true' : 'false') === v ? 'selected' : ''}>${v}</option>`).join('')}
                  </select>
                </div>
                <div class="metric"><div class="label">Suggested</div><div class="value">${(lteSuggest.suggested && lteSuggest.suggested.provider) ? `${lteSuggest.suggested.provider} (${lteSuggest.suggested.apn})` : '-'}</div></div>
              </div>
              <div class="controls">
                <button onclick="applySuggestedApn('${(lteSuggest.suggested && lteSuggest.suggested.id) || ''}')">Apply Suggested</button>
              </div>
            </details>
            <details class="menu" style="margin-top:8px;">
              <summary>APN Presets</summary>
              <div class="menu-content compact-grid">
                <div class="metric">
                  <div class="label">Provider</div>
                  <select class="compact" id="lte-apn-profile" onchange="updateApnFields()">
                    ${(lteOptions.options || []).map(opt => `<option value="${opt.id}" ${suggestedId === opt.id ? 'selected' : ''}>${opt.country} - ${opt.provider} (${opt.apn})</option>`).join('')}
                  </select>
                </div>
                <div class="metric"><div class="label">Custom APN</div><input id="lte-apn-custom" placeholder="optional" value="" /></div>
                <div class="metric">
                  <div class="label">IPv4 Method</div>
                  <select class="compact" id="lte-ipv4-method">
                    ${['auto', 'disabled'].map(v => `<option value="${v}">${v}</option>`).join('')}
                  </select>
                </div>
                <div class="metric">
                  <div class="label">IPv6 Method</div>
                  <select class="compact" id="lte-ipv6-method">
                    ${['auto', 'disabled'].map(v => `<option value="${v}">${v}</option>`).join('')}
                  </select>
                </div>
                <div class="metric">
                  <div class="label">Remember For This SIM</div>
                  <select class="compact" id="lte-apn-remember">
                    ${['true', 'false'].map(v => `<option value="${v}" ${v === 'true' ? 'selected' : ''}>${v}</option>`).join('')}
                  </select>
                </div>
              </div>
              <div class="controls">
                <button onclick="applyLteApn()">Apply APN</button>
              </div>
            </details>
            <div class="route" id="lte-apn-details">Select a provider to see APN settings.</div>
            ${lteSuggest.override && lteSuggest.override.apn ? `<div class="chip">Saved override for SIM: ${lteSuggest.override.apn} (v4 ${lteSuggest.override.ipv4_method}, v6 ${lteSuggest.override.ipv6_method})</div>` : ''}
            <div class="hint">APN change will reconnect LTE for a few seconds.</div>
          `;
          updateApnFields();

          document.getElementById('services').innerHTML = `
            <ul>
              ${services.map(s => {
                const url = getServiceUrl(s);
                return `<li><strong>${s.name}</strong>: ${s.active ? 'UP' : 'DOWN'}${s.ports ? ` (${s.ports.join(', ')})` : ''}${url ? ` <a class="service-link" href="${url}" target="_blank" rel="noreferrer">Open</a>` : ''}</li>`;
              }).join('')}
            </ul>
          `;

          document.getElementById('samba-panel').innerHTML = `
            <div class="compact-grid">
              <div class="metric"><div class="label">Running</div><div class="value">${samba.running ? 'UP' : 'DOWN'}</div></div>
              <div class="metric"><div class="label">NetBIOS</div><div class="value">${samba.nmbd_running ? 'UP' : 'DOWN'}</div></div>
              <div class="metric"><div class="label">Config</div><div class="value">${samba.config_path || '-'}</div></div>
              <div class="metric"><div class="label">Shares</div><div class="value">${(samba.shares || []).join(', ') || '-'}</div></div>
            </div>
            <div class="controls">
              <button onclick="controlSamba('start')">Start</button>
              <button onclick="controlSamba('stop')">Stop</button>
              <button class="secondary" onclick="controlSamba('restart')">Restart</button>
            </div>
            <div class="pill">Samba User</div>
            <div class="compact-grid" style="margin-top:8px;">
              <div class="metric"><div class="label">Username</div><input id="samba-username" placeholder="user" /></div>
              <div class="metric"><div class="label">Password</div><input id="samba-password" type="password" placeholder="new password" /></div>
            </div>
            <div class="controls">
              <button onclick="setSambaPassword()">Set Password</button>
            </div>
            <div class="hint">${samba.smbpasswd_available ? 'Password updates use smbpasswd.' : 'smbpasswd not available.'}</div>
          `;

          document.getElementById('service-lan').innerHTML = `
            <div class="compact-grid">
              <div class="metric"><div class="label">Interface</div><div class="value">${serviceLan.interface}</div></div>
              <div class="metric"><div class="label">IPv4 Mode</div><div class="value">${serviceLan.connection_mode_ipv4 || '-'}</div></div>
              <div class="metric"><div class="label">IPv4 Gateway</div><div class="value">${serviceLan.gateway_ipv4 || '-'}</div></div>
              <div class="metric"><div class="label">IPv4 Subnet</div><div class="value">${serviceLan.ipv4_subnet || '-'}</div></div>
              <div class="metric"><div class="label">DHCP Range</div><div class="value">${serviceLan.dhcp_range_ipv4 || '-'}</div></div>
              <div class="metric"><div class="label">DHCP Listener</div><div class="value">${serviceLan.dhcp_listener_active ? 'UP' : 'DOWN'}</div></div>
              <div class="metric"><div class="label">IPv6 Gateway</div><div class="value">${serviceLan.gateway_ipv6 || '-'}</div></div>
              <div class="metric"><div class="label">IPv6 Prefix</div><div class="value">${serviceLan.prefix_ipv6 || '-'}</div></div>
              <div class="metric"><div class="label">Internet</div><div class="value">${serviceLan.internet_enabled ? 'ON' : 'OFF'}</div></div>
            </div>
            <div class="pill">Editable Controls</div>
            <div class="compact-grid" style="margin-top:8px;">
              <div class="metric"><div class="label">Interface</div><input id="service-lan-interface" value="${draftValue('service_lan.interface', serviceLan.interface)}" /></div>
              <div class="metric"><div class="label">IPv4 Gateway</div><input id="service-lan-ipv4-gateway" value="${draftValue('service_lan.ipv4_gateway', serviceLan.gateway_ipv4 || '')}" /></div>
              <div class="metric"><div class="label">IPv4 Subnet</div><input id="service-lan-ipv4-subnet" value="${draftValue('service_lan.ipv4_subnet', serviceLan.ipv4_subnet || '')}" /></div>
              <div class="metric"><div class="label">DHCP Range</div><input id="service-lan-dhcp-range" value="${draftValue('service_lan.dhcp_range', serviceLan.dhcp_range_ipv4 || '')}" /></div>
              <div class="metric"><div class="label">IPv6 Gateway</div><input id="service-lan-ipv6-gateway" value="${draftValue('service_lan.ipv6_gateway', serviceLan.gateway_ipv6 || '')}" /></div>
              <div class="metric"><div class="label">IPv6 Prefix</div><input id="service-lan-ipv6-prefix" value="${draftValue('service_lan.ipv6_prefix', serviceLan.prefix_ipv6 || '')}" /></div>
              <div class="metric">
                <div class="label">Enable IPv4</div>
                <select id="service-lan-enable-ipv4">
                  ${['true', 'false'].map(v => `<option value="${v}" ${draftValue('service_lan.enable_ipv4', serviceLan.ipv4_enabled ? 'true' : 'false') === v ? 'selected' : ''}>${v}</option>`).join('')}
                </select>
              </div>
              <div class="metric">
                <div class="label">Enable IPv6</div>
                <select id="service-lan-enable-ipv6">
                  ${['true', 'false'].map(v => `<option value="${v}" ${draftValue('service_lan.enable_ipv6', serviceLan.ipv6_enabled ? 'true' : 'false') === v ? 'selected' : ''}>${v}</option>`).join('')}
                </select>
              </div>
            </div>
            <div class="controls">
              <button onclick="saveServiceLanConfig()">Save Config</button>
              <button onclick="toggleServiceLanInternet('on')">Enable Internet</button>
              <button class="secondary" onclick="toggleServiceLanInternet('off')">Disable Internet</button>
            </div>
          `;

          document.getElementById('main-lan').innerHTML = `
            <div class="compact-grid">
              <div class="metric"><div class="label">Profile</div><div class="value">${lanProfile.name}</div></div>
              <div class="metric"><div class="label">Role</div><div class="value">${lanProfile.role}</div></div>
              <div class="metric"><div class="label">Target</div><div class="value">${lanProfile.target_interface}</div></div>
              <div class="metric"><div class="label">State</div><div class="value">${lanProfile.target_interface_status.state || '-'}</div></div>
              <div class="metric"><div class="label">NetworkManager</div><div class="value">${lanProfile.target_interface_status.nm_state || 'not visible'}</div></div>
              <div class="metric"><div class="label">Active Connection</div><div class="value">${lanProfile.target_interface_status.nm_connection || '-'}</div></div>
              <div class="metric"><div class="label">Current IPv4</div><div class="value">${(lanProfile.target_interface_status.ipv4 || []).join(', ') || '-'}</div></div>
              <div class="metric"><div class="label">Current IPv6</div><div class="value">${(lanProfile.target_interface_status.ipv6 || []).join(', ') || '-'}</div></div>
              <div class="metric"><div class="label">Desired IPv4 Mode</div><div class="value">${lanProfile.ipv4_mode}</div></div>
              <div class="metric"><div class="label">IPv4 Block</div><div class="value">${lanProfile.ipv4_subnet}</div></div>
              <div class="metric"><div class="label">IPv4 Address</div><div class="value">${lanProfile.ipv4_address}</div></div>
              <div class="metric"><div class="label">DHCP Range</div><div class="value">${lanProfile.dhcp_range}</div></div>
              <div class="metric"><div class="label">IPv6 Mode</div><div class="value">${lanProfile.ipv6_mode}</div></div>
              <div class="metric"><div class="label">IPv6 Address</div><div class="value">${lanProfile.ipv6_address}</div></div>
              <div class="metric"><div class="label">IPv6 Prefix</div><div class="value">${lanProfile.ipv6_prefix}</div></div>
              <div class="metric"><div class="label">DNS Servers</div><div class="value">${(lanProfile.dns_servers || []).join(', ') || '-'}</div></div>
              <div class="metric"><div class="label">DNS Search</div><div class="value">${lanProfile.dns_search || '-'}</div></div>
              <div class="metric"><div class="label">Internet</div><div class="value">${lanProfile.internet_enabled ? 'ON' : 'OFF'}</div></div>
            </div>
            <div class="pill">Editable Controls</div>
            <div class="compact-grid" style="margin-top:8px;">
              <div class="metric">
                <div class="label">Target Interface</div>
                <select id="main-lan-target-interface">
                  ${interfaces.filter(i => i.physical && i.role === 'ethernet').map(i => `<option value="${i.name}" ${draftValue('main_lan.target_interface', lanProfile.target_interface) === i.name ? 'selected' : ''}>${i.name}</option>`).join('')}
                </select>
              </div>
              <div class="metric">
                <div class="label">Role</div>
                <select id="main-lan-role">
                  ${['multi-purpose', 'home-lab', 'service', 'isolated'].map(v => `<option value="${v}" ${draftValue('main_lan.role', lanProfile.role) === v ? 'selected' : ''}>${v}</option>`).join('')}
                </select>
              </div>
              <div class="metric">
                <div class="label">IPv4 Mode</div>
                <select id="main-lan-ipv4-mode">
                  ${['shared', 'manual', 'disabled'].map(v => `<option value="${v}" ${draftValue('main_lan.ipv4_mode', lanProfile.ipv4_mode) === v ? 'selected' : ''}>${v}</option>`).join('')}
                </select>
              </div>
              <div class="metric"><div class="label">IPv4 Address</div><input id="main-lan-ipv4-address" value="${draftValue('main_lan.ipv4_address', lanProfile.ipv4_address || '')}" /></div>
              <div class="metric"><div class="label">IPv4 Block</div><input id="main-lan-ipv4-subnet" value="${draftValue('main_lan.ipv4_subnet', lanProfile.ipv4_subnet || '')}" /></div>
              <div class="metric"><div class="label">DHCP Range</div><input id="main-lan-dhcp-range" value="${draftValue('main_lan.dhcp_range', lanProfile.dhcp_range || '')}" /></div>
              <div class="metric">
                <div class="label">IPv6 Mode</div>
                <select id="main-lan-ipv6-mode">
                  ${['routed', 'manual', 'disabled'].map(v => `<option value="${v}" ${draftValue('main_lan.ipv6_mode', lanProfile.ipv6_mode) === v ? 'selected' : ''}>${v}</option>`).join('')}
                </select>
              </div>
              <div class="metric"><div class="label">IPv6 Address</div><input id="main-lan-ipv6-address" value="${draftValue('main_lan.ipv6_address', lanProfile.ipv6_address || '')}" /></div>
              <div class="metric"><div class="label">IPv6 Prefix</div><input id="main-lan-ipv6-prefix" value="${draftValue('main_lan.ipv6_prefix', lanProfile.ipv6_prefix || '')}" /></div>
              <div class="metric"><div class="label">DNS Servers</div><input id="main-lan-dns-servers" value="${draftValue('main_lan.dns_servers', (lanProfile.dns_servers || []).join(', '))}" /></div>
              <div class="metric"><div class="label">DNS Search</div><input id="main-lan-dns-search" value="${draftValue('main_lan.dns_search', lanProfile.dns_search || '')}" /></div>
            </div>
            <div class="controls">
              <button onclick="saveMainLanConfig()">Save Config</button>
              <button onclick="applyMainLan()">Apply Main LAN</button>
              <button onclick="restartMainLan()">Restart Connection</button>
              <button onclick="toggleMainLanInternet('on')">Enable Internet</button>
              <button class="secondary" onclick="toggleMainLanInternet('off')">Disable Internet</button>
            </div>
            <div class="hint">Shared mode needs host-compatible NetworkManager for full DHCP automation. Static fallback can still assign the LAN IP to the port.</div>
          `;

          document.getElementById('wifi-panel').innerHTML = `
            <div class="compact-grid">
              <div class="metric"><div class="label">Interface</div><div class="value">${wifi.interface}</div></div>
              <div class="metric"><div class="label">State</div><div class="value">${wifi.device.state || '-'}</div></div>
              <div class="metric"><div class="label">NetworkManager</div><div class="value">${wifi.device.nm_state || '-'}</div></div>
              <div class="metric"><div class="label">Current IPv4</div><div class="value">${(wifi.device.ipv4 || []).join(', ') || '-'}</div></div>
              <div class="metric"><div class="label">Current IPv6</div><div class="value">${(wifi.device.ipv6 || []).join(', ') || '-'}</div></div>
            </div>
            <div class="pill">Wi-Fi Controls</div>
            <div class="compact-grid" style="margin-top:8px;">
              <div class="metric">
                <div class="label">Interface</div>
                <select id="wifi-interface">
                  ${interfaces.filter(i => i.role === 'wifi').map(i => `<option value="${i.name}" ${draftValue('wifi.interface', wifi.interface) === i.name ? 'selected' : ''}>${i.name}</option>`).join('')}
                </select>
              </div>
              <div class="metric">
                <div class="label">Mode</div>
                <select id="wifi-mode">
                  ${['client', 'hotspot'].map(v => `<option value="${v}" ${draftValue('wifi.mode', wifi.config.mode) === v ? 'selected' : ''}>${v}</option>`).join('')}
                </select>
              </div>
              <div class="metric"><div class="label">Client SSID</div><input id="wifi-ssid" value="${draftValue('wifi.ssid', wifi.config.ssid || '')}" /></div>
              <div class="metric"><div class="label">Client Password</div><input id="wifi-password" type="password" value="${draftValue('wifi.password', wifi.config.password || '')}" /></div>
              <div class="metric"><div class="label">Hotspot SSID</div><input id="wifi-hotspot-ssid" value="${draftValue('wifi.hotspot_ssid', wifi.config.hotspot_ssid || '')}" /></div>
              <div class="metric"><div class="label">Hotspot Password</div><input id="wifi-hotspot-password" type="password" value="${draftValue('wifi.hotspot_password', wifi.config.hotspot_password || '')}" /></div>
              <div class="metric">
                <div class="label">IPv4 Method</div>
                <select id="wifi-ipv4-method">
                  ${['auto', 'manual', 'shared'].map(v => `<option value="${v}" ${draftValue('wifi.ipv4_method', wifi.config.ipv4_method) === v ? 'selected' : ''}>${v}</option>`).join('')}
                </select>
              </div>
              <div class="metric"><div class="label">IPv4 Address</div><input id="wifi-ipv4-address" value="${draftValue('wifi.ipv4_address', wifi.config.ipv4_address || '')}" /></div>
              <div class="metric">
                <div class="label">IPv6 Method</div>
                <select id="wifi-ipv6-method">
                  ${['auto', 'manual', 'disabled'].map(v => `<option value="${v}" ${draftValue('wifi.ipv6_method', wifi.config.ipv6_method) === v ? 'selected' : ''}>${v}</option>`).join('')}
                </select>
              </div>
              <div class="metric"><div class="label">IPv6 Address</div><input id="wifi-ipv6-address" value="${draftValue('wifi.ipv6_address', wifi.config.ipv6_address || '')}" /></div>
            </div>
            <div class="controls">
              <button onclick="saveWifiConfig()">Save Wi-Fi Config</button>
              <button onclick="applyWifi()">Apply Wi-Fi</button>
              <button class="secondary" onclick="render()">Rescan</button>
            </div>
            <div class="route">
              <div class="label">Visible Wi-Fi Networks</div>
              <div>${(wifi.scan || []).length ? wifi.scan.map(n => `${n.in_use ? '[*]' : '[ ]'} ${n.ssid} (${n.signal}%, ${n.security || 'open'})`).join('<br>') : 'No scan results'}</div>
            </div>
            <div class="route">
              <div class="label">RFKill</div>
              <div>${(wifi.rfkill || []).length ? wifi.rfkill.map(r => `${r.name || r.type}: soft=${r.soft} hard=${r.hard}`).join('<br>') : 'No rfkill entries'}</div>
            </div>
            <div class="hint">${(wifi.notes || []).join(' ')}</div>
          `;

          document.getElementById('interfaces').innerHTML = `
            <div class="grid">
              ${interfaces.map(i => `
                <div class="card">
                  <div class="label">${i.name}</div>
                  <div class="value">${i.state}</div>
                  <div><span class="label">MAC:</span> ${i.mac || '-'}</div>
                  <div><span class="label">IPv4:</span> ${(i.ipv4 || []).join(', ') || '-'}</div>
                  <div><span class="label">IPv6:</span> ${(i.ipv6 || []).join(', ') || '-'}</div>
                  <div><span class="label">Role:</span> ${i.role || '-'}</div>
                  <div><span class="label">MTU:</span> ${i.mtu}</div>
                  ${i.physical ? `
                    <div class="controls">
                      <button onclick="setLinkState('${i.name}', 'up')">Link Up</button>
                      <button class="secondary" onclick="setLinkState('${i.name}', 'down')">Link Down</button>
                    </div>
                  ` : ''}
                </div>
              `).join('')}
            </div>
          `;

          document.getElementById('service-lan-clients').innerHTML = serviceLanClients.length
            ? `
              <div class="grid">
                ${serviceLanClients.map(c => `
                  <div class="card">
                    <div><span class="label">IP:</span> <span class="value">${c.ip}</span></div>
                    <div><span class="label">Interface:</span> ${c.interface || '-'}</div>
                    <div><span class="label">Family:</span> ${c.family || '-'}</div>
                    <div><span class="label">MAC:</span> ${c.mac || '-'}</div>
                    <div><span class="label">Hostname:</span> ${c.hostname || '-'}</div>
                    <div><span class="label">State:</span> ${c.state || '-'}</div>
                  </div>
                `).join('')}
              </div>
            `
            : '<div class="label">No clients detected</div>';

          document.getElementById('active-sessions').innerHTML = activeSessions.length
            ? `
              <div class="grid">
                ${activeSessions.map(s => `
                  <div class="card">
                    <div><span class="label">Service:</span> <span class="value">${s.service}</span></div>
                    <div><span class="label">Interface:</span> ${s.interface || '-'}</div>
                    <div><span class="label">Family:</span> ${s.family || '-'}</div>
                    <div><span class="label">Local:</span> ${s.local_address}:${s.local_port}</div>
                    <div><span class="label">Peer:</span> ${s.peer_address}:${s.peer_port}</div>
                  </div>
                `).join('')}
              </div>
            `
            : '<div class="label">No active sessions detected</div>';

          [
            ['main-lan-target-interface', 'main_lan.target_interface'],
            ['main-lan-role', 'main_lan.role'],
            ['main-lan-ipv4-mode', 'main_lan.ipv4_mode'],
            ['main-lan-ipv4-address', 'main_lan.ipv4_address'],
            ['main-lan-ipv4-subnet', 'main_lan.ipv4_subnet'],
            ['main-lan-dhcp-range', 'main_lan.dhcp_range'],
            ['main-lan-ipv6-mode', 'main_lan.ipv6_mode'],
            ['main-lan-ipv6-address', 'main_lan.ipv6_address'],
            ['main-lan-ipv6-prefix', 'main_lan.ipv6_prefix'],
            ['main-lan-dns-servers', 'main_lan.dns_servers'],
            ['main-lan-dns-search', 'main_lan.dns_search'],
            ['service-lan-interface', 'service_lan.interface'],
            ['service-lan-ipv4-gateway', 'service_lan.ipv4_gateway'],
            ['service-lan-ipv4-subnet', 'service_lan.ipv4_subnet'],
            ['service-lan-dhcp-range', 'service_lan.dhcp_range'],
            ['service-lan-ipv6-gateway', 'service_lan.ipv6_gateway'],
            ['service-lan-ipv6-prefix', 'service_lan.ipv6_prefix'],
            ['service-lan-enable-ipv4', 'service_lan.enable_ipv4'],
            ['service-lan-enable-ipv6', 'service_lan.enable_ipv6'],
            ['wifi-interface', 'wifi.interface'],
            ['wifi-mode', 'wifi.mode'],
            ['wifi-ssid', 'wifi.ssid'],
            ['wifi-password', 'wifi.password'],
            ['wifi-hotspot-ssid', 'wifi.hotspot_ssid'],
            ['wifi-hotspot-password', 'wifi.hotspot_password'],
            ['wifi-ipv4-method', 'wifi.ipv4_method'],
            ['wifi-ipv4-address', 'wifi.ipv4_address'],
            ['wifi-ipv6-method', 'wifi.ipv6_method'],
            ['wifi-ipv6-address', 'wifi.ipv6_address'],
          ].forEach(([id, key]) => bindDraft(id, key));
        }

        render();
        setInterval(render, 10000);
      </script>
    </body>
    </html>
    """
