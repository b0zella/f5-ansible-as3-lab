# F5 BIG-IP Automation with Ansible + AS3

Declarative app delivery for F5 BIG-IP. Apps are defined as data in Git,
rendered into an AS3 declaration by an Ansible role, validated, and pushed to
BIG-IP through a Jenkins pipeline with manual approval and automatic rollback.

```
apps.yml (source of truth)
   │
   ▼
Ansible role "as3" ──► input validation (assert)
   │
   ▼
Jinja2 template ──► build/as3_<host>.json ──► Python validator
   │
   ▼  (only with -e as3_deploy=true, after Jenkins approval)
GET current declaration (backup) ──► POST /mgmt/shared/appsvcs/declare
   │                                        │
   └──────── rescue: POST backup ◄── on failure
```

## What it shows

| Skill | Where |
|---|---|
| Reusable role, defaults vs. inventory vars | `roles/as3/`, `inventory/group_vars/bigip/` |
| Jinja2 templating | `roles/as3/templates/as3.yml.j2` |
| Input validation with `assert`, loops, `subelements` | `roles/as3/tasks/validate_input.yml` |
| Idempotency (AS3 "no change" → `changed=0`) | `roles/as3/tasks/deploy.yml` |
| Error handling + rollback (`block/rescue`) | `roles/as3/tasks/deploy.yml` |
| Secrets with Ansible Vault | `inventory/group_vars/bigip/vault.yml.example` |
| F5 iControl REST / AS3 API integration | `uri` tasks in `deploy.yml` |
| Python validation (IPs, ports, references, VIP collisions) | `scripts/validate_as3.py` |
| CI/CD with lint, artifact, approval gate | `Jenkinsfile` |

## Phase 1: run locally (no BIG-IP needed)

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt

ansible-lint playbooks/ roles/
ansible-playbook playbooks/site.yml        # renders + validates
cat build/as3_bigip-lab.json               # the declaration
ansible-playbook playbooks/site.yml        # run again: changed=0 (idempotent)
```

Try breaking it on purpose: give two apps the same VIP and port, or set a
member IP to `10.1.20.999`. The run should fail before anything is deployed.

> Keep the repo under your WSL home (`/home/<you>`), not `/mnt/c/...`.
> Ansible ignores `ansible.cfg` in world-writable directories.

## Phase 2: deploy to a real BIG-IP

1. Launch a BIG-IP VE (e.g. AWS Marketplace PAYG) with AS3 installed.
   Check the version: `GET https://<mgmt>/mgmt/shared/appsvcs/info`, then set
   `as3_schema_version` in `roles/as3/defaults/main.yml` to match.
2. Set `bigip_host` in `inventory/hosts.ini` to the management IP.
3. Create and encrypt the vault:
   ```bash
   cp inventory/group_vars/bigip/vault.yml.example inventory/group_vars/bigip/vault.yml
   # edit the password, then:
   ansible-vault encrypt inventory/group_vars/bigip/vault.yml
   ```
4. Deploy:
   ```bash
   ansible-playbook playbooks/site.yml -e as3_deploy=true --ask-vault-pass
   ```
5. Run it again and confirm `changed=0`. Delete `api_app` from `apps.yml`,
   redeploy, and watch AS3 remove it from the BIG-IP.
6. **Stop the instance when you're done.**

## Jenkins

Create a Secret-file credential named `ansible-vault-pass`. Run the job with
`DEPLOY=false` to lint/render/validate only. With `DEPLOY=true` it pauses for
approval before pushing. Your Jenkins agent needs `python3` and `python3-venv`.

## Roadmap

- [ ] Drift check: compare the live declaration to the rendered one on a schedule
- [ ] Imperative version with `f5networks.f5_modules` for comparison
- [ ] GTM/DNS: wide IPs and GSLB pools (`GSLB_Domain`, `GSLB_Pool`)
- [ ] Run from AWX with job templates and RBAC
- [ ] Molecule tests for the role
