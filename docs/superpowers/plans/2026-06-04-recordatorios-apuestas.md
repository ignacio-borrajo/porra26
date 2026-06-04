# Plan — Recordatorios de apuestas → Teams

**Spec:** `docs/superpowers/specs/2026-06-04-recordatorios-apuestas-design.md`
**Fecha:** 2026-06-04

Implementación TDD en orden de capas. Cada paso deja la suite verde antes de pasar al siguiente. Commits separados por capa, estilo conventional.

---

## Paso 1 — Modelo `BetsReminderLog` + migración

**Tests primero:** ninguno todavía (solo modelo + migración).

**Código:**
- En `competition/models.py`: añadir `BetsReminderLog` con choices, `UniqueConstraint(match, kind)`, `Index(sent_at)`, `pending_names` JSONField.
- `python manage.py makemigrations competition` → `0NNN_betsreminderlog.py`.
- Revisar migración generada.

**Verificación:** `pytest -q` → 404 pasan (sin tests nuevos aún). `python manage.py migrate --plan` → muestra la nueva migración.

**Commit:** `feat(reminders): modelo BetsReminderLog`

---

## Paso 2 — Servicio de detección (`services/reminders.py`)

**Tests primero** (`competition/tests/test_reminder_detection.py`):
- `test_pending_bettors_excludes_those_who_bet`
- `test_pending_bettors_excludes_inactive_users`
- `test_pending_bettors_excludes_non_jugador`
- `test_pending_bettors_includes_gestor_who_plays`
- `test_pending_bettors_ordered_by_name`
- `test_matches_due_t_minus_4h_returns_match_inside_window`
- `test_matches_due_excludes_match_after_closure`
- `test_matches_due_excludes_match_with_existing_log_for_kind`
- `test_matches_due_includes_match_with_log_for_other_kind`
- `test_matches_due_t_minus_2_5h_window`

**Código:** `competition/services/reminders.py`
- `get_pending_bettors(match) -> list[User]`
- `matches_due_for_kind(kind) -> QuerySet[Match]`

**Verificación:** `pytest competition/tests/test_reminder_detection.py -q` verde.

**Commit:** `feat(reminders): detección de rezagados y ventanas de aviso`

---

## Paso 3 — Servicio de envío (`services/reminder_email.py`)

**Tests primero** (`competition/tests/test_reminder_email_service.py`):
- `test_send_creates_email_when_pending`
- `test_send_creates_log_when_pending`
- `test_send_no_email_when_no_pending`
- `test_send_no_log_when_no_pending`
- `test_send_subject_includes_prefix_and_teams`
- `test_send_subject_includes_kickoff_local_format`
- `test_send_body_html_lists_pending_names`
- `test_send_body_plain_lists_pending_names`
- `test_send_body_includes_remaining_time_for_4h_kind`
- `test_send_body_includes_remaining_time_for_2_5h_kind`
- `test_send_body_includes_remaining_time_for_manual_kind`
- `test_send_truncates_names_above_30`
- `test_send_auto_kind_is_idempotent`
- `test_send_manual_kind_updates_existing_row`
- `test_send_raises_value_error_after_closure`
- `test_send_creates_audit_log`
- `test_send_log_has_pending_count_and_names_snapshot`

**Código:** `competition/services/reminder_email.py`
- `send_reminder_email(match, kind) -> BetsReminderLog | None`
- Helpers internos para construir HTML y plain.

**Verificación:** `pytest competition/tests/test_reminder_email_service.py -q` verde.

**Commit:** `feat(reminders): servicio send_reminder_email`

---

## Paso 4 — Management command

**Tests primero** (`competition/tests/test_send_match_reminders_command.py`):
- `test_command_sends_both_kinds_in_window`
- `test_command_continues_on_individual_error`
- `test_command_dry_run_does_not_send`
- `test_command_match_id_filter`
- `test_command_kind_filter`
- `test_command_skips_match_outside_window`

**Código:** `competition/management/commands/send_match_reminders.py`
- Args: `--match-id`, `--kind`, `--dry-run`.
- Captura excepciones por match individualmente.

**Verificación:** `pytest competition/tests/test_send_match_reminders_command.py -q` verde.

**Commit:** `feat(reminders): management command send_match_reminders`

---

## Paso 5 — Endpoints API

**Tests primero** (`competition/tests/test_reminder_api_endpoints.py`):
- `test_disparar_requires_auth`
- `test_disparar_with_bearer_returns_summary_json`
- `test_disparar_with_gestor_session_returns_summary_json`
- `test_disparar_sends_due_matches`
- `test_disparar_skips_when_no_pending`
- `test_enviar_requires_auth`
- `test_enviar_with_gestor_session_returns_sent_true`
- `test_enviar_returns_no_pending_when_all_bet`
- `test_enviar_returns_409_when_closed`
- `test_enviar_html_redirects_with_flash`

**Código:**
- En `competition/api/views.py`: añadir `recordatorios_disparar`, `recordatorio_enviar`.
- En `competition/api/urls.py`: registrar rutas.

**Verificación:** `pytest competition/tests/test_reminder_api_endpoints.py -q` verde.

**Commit:** `feat(reminders): endpoints disparar y enviar manual`

---

## Paso 6 — UI en `manage_results.html`

**Tests primero** (`competition/tests/test_manage_results_reminders.py`):
- `test_upcoming_section_shows_reminder_button`
- `test_upcoming_section_shows_pending_pill_with_count_when_some_pending`
- `test_upcoming_section_shows_green_pill_when_all_bet`
- `test_upcoming_section_disables_button_when_no_pending`
- `test_upcoming_section_shows_last_reminder_tooltip_when_log_exists`
- `test_upcoming_section_no_reminder_widget_for_closed_match`

**Código:**
- En `competition/views.py` (`ManageResultsView.get`): precalcular `pending_counts` (dict match_id → int) y `last_reminders` (dict match_id → BetsReminderLog).
- En `templates/competition/manage_results.html`: extender la sección `PRÓXIMOS` con pill + botón.

**Verificación:** `pytest competition/tests/test_manage_results_reminders.py -q` verde.

**Commit:** `feat(reminders): UI con pill y botón en /resultados/`

---

## Paso 7 — Settings + .env.example

**Código:**
- `porra26/settings/base.py`: añadir `TEAMS_REMINDER_SUBJECT_PREFIX`.
- `.env.example`: añadir línea.
- `porra26/settings/test.py`: forzar prefix conocido si no estuviera.

**Verificación:** suite entera `pytest -q` verde.

**Commit:** `chore(reminders): settings y .env.example`

---

## Paso 8 — GitHub Actions workflow

**Código:**
- Crear `.github/workflows/match-reminders.yml` con schedule + workflow_dispatch + curl al endpoint.

**Verificación:** YAML válido (`actionlint` si está disponible, si no inspección visual). No se ejecuta hasta merge.

**Commit:** `ci(reminders): GitHub Actions workflow para disparar cron`

---

## Paso 9 — Docs

**Código:**
- `docs/TEAMS_FLOW.md`: nueva sección "Flow de recordatorios".
- `docs/RUNBOOK.md`: entrada "Verificar recordatorios".
- `docs/PLAN.md`: marcar feature.

**Verificación:** revisión visual.

**Commit:** `docs(reminders): TEAMS_FLOW, RUNBOOK, PLAN actualizados`

---

## Paso 10 — Verificación final

- `pytest -q` → todos verdes.
- `ruff check .` y `ruff format --check .` → limpios.
- `python manage.py check` → limpio.
- `python manage.py makemigrations --dry-run` → "No changes detected".

**Commit:** (si hay ajustes de format) `style(reminders): ruff format`

---

## Checklist final

- [ ] Spec y plan commiteados.
- [ ] 10 pasos completados con commits separados.
- [ ] Suite verde (404 + ~50 nuevos = ~450+).
- [ ] Ruff limpio.
- [ ] `python manage.py check` limpio.
- [ ] PR creada hacia `main`.
- [ ] PR mergeada.
- [ ] `main` pusheada.
