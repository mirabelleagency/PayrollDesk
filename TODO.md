# Task List

- [ ] Update `app/routers/schedules.py::export_dashboard_excel` to accept the selected year (and any active quick range filters) so exports mirror the dashboard view.
- [ ] Add regression coverage around `_gather_dashboard_data` for non-current years to ensure the schedules dashboard shows historical cycles and summaries correctly.
- [ ] Spot-check the redesigned analytics filter card (`app/templates/analytics/index.html`, `app/static/css/styles.css`) on key breakpoints to confirm layout and focus styles hold up.
- [ ] Run the FastAPI test suite (`pytest`) after the schedule and analytics UI changes to verify no regressions.
