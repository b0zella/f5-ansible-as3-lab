#!/usr/bin/env python3
"""Sanity-check a rendered AS3 declaration before it goes near a BIG-IP.

Catches the mistakes that cause failed or dangerous deploys:
  - wrong top-level structure
  - invalid IP addresses or ports
  - services pointing at pools/monitors/TLS profiles that don't exist
  - two services listening on the same VIP:port

Usage: python3 validate_as3.py build/as3_bigip-lab.json
Exit code 0 = good, 1 = problems found (pipeline should stop).
"""
import ipaddress
import json
import sys

SERVICE_CLASSES = {"Service_HTTP", "Service_HTTPS", "Service_TCP", "Service_UDP"}
TENANT_RESERVED = {"class", "schemaVersion", "id", "label", "remark", "Common", "controls"}


def check_ip(value, where, errors):
    try:
        ipaddress.ip_address(value)
    except ValueError:
        errors.append(f"{where}: '{value}' is not a valid IP address")


def check_port(value, where, errors):
    if not isinstance(value, int) or not 1 <= value <= 65535:
        errors.append(f"{where}: port '{value}' out of range")


def validate(doc):
    errors = []
    listeners = {}

    if doc.get("class") != "AS3":
        errors.append("top level: class must be 'AS3'")
    adc = doc.get("declaration", {})
    if adc.get("class") != "ADC":
        errors.append("declaration: class must be 'ADC'")
    if "schemaVersion" not in adc:
        errors.append("declaration: schemaVersion missing")

    tenants = {k: v for k, v in adc.items() if k not in TENANT_RESERVED and isinstance(v, dict)}
    if not tenants:
        errors.append("declaration: no tenants found")

    for t_name, tenant in tenants.items():
        if tenant.get("class") != "Tenant":
            errors.append(f"{t_name}: class must be 'Tenant'")
        apps = {k: v for k, v in tenant.items() if isinstance(v, dict)}
        for a_name, app in apps.items():
            path = f"{t_name}/{a_name}"
            if app.get("class") != "Application":
                errors.append(f"{path}: class must be 'Application'")
            objects = {k: v for k, v in app.items() if isinstance(v, dict)}

            for o_name, obj in objects.items():
                where = f"{path}/{o_name}"
                cls = obj.get("class")

                if cls in SERVICE_CLASSES:
                    port = obj.get("virtualPort")
                    check_port(port, where, errors)
                    for vip in obj.get("virtualAddresses", []):
                        check_ip(vip, where, errors)
                        key = f"{vip}:{port}"
                        if key in listeners:
                            errors.append(f"{where}: {key} already used by {listeners[key]}")
                        listeners[key] = where
                    for ref in ("pool", "serverTLS"):
                        target = obj.get(ref)
                        if isinstance(target, str) and target not in objects:
                            errors.append(f"{where}: {ref} '{target}' not defined in app")

                elif cls == "Pool":
                    members = obj.get("members", [])
                    if not members:
                        errors.append(f"{where}: pool has no members")
                    for m in members:
                        check_port(m.get("servicePort"), where, errors)
                        for addr in m.get("serverAddresses", []):
                            check_ip(addr, where, errors)
                    for mon in obj.get("monitors", []):
                        if isinstance(mon, dict) and "use" in mon and mon["use"] not in objects:
                            errors.append(f"{where}: monitor '{mon['use']}' not defined in app")

                elif cls == "Monitor":
                    if obj.get("timeout", 0) <= obj.get("interval", 0):
                        errors.append(f"{where}: timeout must be greater than interval")

    return errors, listeners


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    with open(sys.argv[1], encoding="utf-8") as fh:
        try:
            doc = json.load(fh)
        except json.JSONDecodeError as exc:
            print(f"FAIL: not valid JSON: {exc}")
            return 1

    errors, listeners = validate(doc)
    if errors:
        print(f"FAIL: {len(errors)} problem(s) in {sys.argv[1]}")
        for e in errors:
            print(f"  - {e}")
        return 1

    print(f"OK: {sys.argv[1]} passed validation ({len(listeners)} listener(s))")
    for key, where in sorted(listeners.items()):
        print(f"  {key:<22} -> {where}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
