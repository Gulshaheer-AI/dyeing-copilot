# Integrated Dyeing Copilot walkthrough

Live app: https://dyeing-copilot-jqoc5pzh9eq9gh5trxc58k.streamlit.app/
Confirm that the optional recovery controls are present; hosting can lag the
repository. Local startup below remains available independently of hosted status.

Launch `.venv/Scripts/python.exe -m streamlit run streamlit_app.py`, then open http://localhost:8501.


## Save and inspect a planned result

1. In **Production planner**, select **Load demo setup**, review rules and explicitly
   **Generate schedule**. Permissions remain opt-in. No AMD call is needed.
2. Open **Review & export**, optionally enter a **History title**, then **Save to history**.
   A second click keeps the same entry. No explanation or review decision is required.
3. Open **Plan history** in the sidebar. Inspect the saved cleaning/on-time metrics,
   switch between **Selected planned result** and the saved baseline/reference, and
   inspect the archived inputs, assumptions, changes and verification expanders.
4. Select **Download saved review package (JSON)**. Return to **Production planner**:
   the active schedule and constraints are unchanged. Repeat with a verified recovery
   result to retain its exact reference/cutoff, protected-work audit and selected priority.

History contains planned results, not actual factory production or measured resources.
Completed/running recovery labels are simulated states at the saved reference cutoff.
Saved planning snapshots are for this session only. Hosted storage may reset after
restart/redeployment; download a copy to keep it. A new session starts with empty
history. No cross-session access or restore-into-planner action is provided.

## Existing integrated planning demonstration

1. **Initial plan.** Production planner is the landing page. Select **Load demo setup**. Review machines and cleaning rules; permissions start off. Explicitly select **Use illustrative cleaning permissions** for this demonstration, then **Generate schedule**. The generated deadline-first baseline is a scenario comparator, not factory performance. Inspect cleaning counts, on-time orders and the smallest deadline buffer. The published-order reference run recorded 34 baseline versus 28 CP-SAT cleaning events; screen values always come from current verified results.
2. **Alternative priorities.** Open **Recovery and alternative objectives** and select **Compare both plan options** to compare Fewer cleanings with More deadline protection under identical constraints. Each option has independent verification and a share of the displayed solve budget. Select the plan to inspect. Identical plans are reported honestly; optimality badges depend on actual solver receipts.
3. **Simulate production having started.** From the verified current plan, enter **Replan from date** `2019-12-01` and **Replan from time** `05:00:00`, then select **Use current verified plan as reference**. Selection does not solve or call AMD. The reference is simulated execution, not telemetry. Completed/running processing and cleaning stay exact; a started cleaning commits the immediately following batch. Future work cannot start before the cutoff.
4. **Preview a disruption.** Under **Request a change**, select **Enter a change manually**, **Machine outage**, and `virtual-Pressure-PolyCotton`. Enter start `2019-12-01 12:00:00`, end `2019-12-02 12:00:00`, then **Preview manual change**. Nothing is applied yet. Alternatively choose **Describe a change with AMD** and enter: `virtual-Pressure-PolyCotton unavailable from 2019-12-01 12:00 to 2019-12-02 12:00.` AMD must return a schema-valid grounded proposal; a failure never silently switches to mock mode.
5. **Confirm and inspect.** Select **Apply changes and reschedule**. Both priorities are solved on the same revised constraints and fixed history. Inspect Recovery impact and before/after order details. In the recorded offline example, 3 completed batches and 2 running batches were preserved; all 35 remained on time. Fewer cleanings retained 28 events; More deadline protection had 30. These are bounded illustrative results, not a guaranteed trade-off or savings claim. Other times may change because the remaining horizon is reoptimised, not solely because of the outage.
6. **Timeline.** In Machine schedule, switch between **Revised verified plan** and **Reference — historical, before disruption**. The red cutoff line and grey revised outage use exact historical timestamps. The reference predates disruption and may violate new availability. Use machine filters and date/day controls; gaps remain idle elapsed time.
7. **Explain, review and export.** In Review & export, explicitly generate a live AMD explanation if configured, or select **Mock demonstration (no API call)**. The latter is always labelled mock. Explanations select exact Python-grounded statements; unsupported questions cannot obtain invented root causes or settings. Save for supervisor review, then record acceptance for further review or rejection. Download the matching planner review package. It includes reference identity, cutoff, operations, selected objective, request/receipt, constraints, solver stages/bounds, verification, recovery changes and applicable review. Pending is not acceptance; acceptance never means production approval.
8. **Stale protection and reset.** Switch plan priority: the previous explanation/review is stale and cannot be accepted/exported as matching the new selection. **Reset to original scenario and reschedule** removes outages, deadline overrides and execution recovery while retaining audit history.
9. **Conflict example.** After selecting the same December cutoff, preview a Pressure-machine outage `2019-12-01 04:00:00` to `2019-12-01 06:00:00`. It overlaps protected work and must report: "This outage overlaps work preserved from the reference plan. Interrupted-batch recovery is not supported." Nothing is applied. A deadline earlier than fixed completion is also blocked. Encoded infeasibility and a time limit without a candidate have different messages; neither permits a current invalid export.

The expandable **Evidence** section shows a separate offline permission sensitivity experiment, not the current recovery case. It retains the no-exemption result and reports bounded statuses.

## Four distinct kinds of evidence

- Published Sitara order records: 35 distinct orders; recorded water total 47,950 unresolved source units.
- Hypothetical schedules: virtual machines, assumed calendars/durations/cleaning permissions. No actual factory approval or measured savings.
- Synthetic daily monitoring: 731 synthetic days, frozen CPU-trained models and historical evaluation, kept separate from orders.
- AMD inference: only an actual successful API receipt establishes live inference. This release used offline/mocked explanations and local request screening; the new live corpus is explicitly opt-in.

The fixed offline recovery artifact is `reports/integrated_recovery_demo_v1.json`. To make another bounded offline run without overwriting it:

```powershell
.venv/Scripts/python.exe tools/integrated_recovery_demo.py --output reports/integrated_recovery_demo_replay.json
```

Factory-data validation, approved SOPs, independent recipe/quality compatibility, equipment calendars and production validation remain outstanding. There is no completed safety-monitoring or autonomous-control claim.
