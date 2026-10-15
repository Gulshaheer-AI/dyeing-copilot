# Dyeing Copilot: short demo walkthrough

1. Open **Production planner**, the default landing page. Point out **Published orders · Illustrative machines and cleaning rules**. The 35 published Sitara orders are real-origin information; machines, calendar and cleaning permissions are hypothetical.
2. Select **Load demo setup**. Review the machine list. Leave **Use illustrative cleaning permissions** unchecked for the first run. Select **Generate schedule**. Nothing calls AMD automatically.
3. Lead with **Cleaning events**, **Orders on time** and **Smallest deadline buffer**. The deadline-first baseline is generated on the same effective constraints and independently verified. Counts are computed afresh, so do not promise a fixed difference. A missing valid baseline is reported as unavailable.
4. In **Machine schedule**, select a machine and use Previous day / Next day or the start-date picker. The initial window covers approximately 24 hours from actual activity. Production blocks show order IDs; amber blocks are cleaning, including terminal cleanup; grey intervals are unavailable. **Show full schedule** preserves elapsed time. Expand the detailed table to confirm exact timestamps.
5. In **Request a change**, choose **Enter a change manually**. Select order **12**, enter deadline **2019-12-23 18:15**, and select **Preview manual change**. Show the old and proposed values. Nothing changes until **Apply changes and reschedule**. Inspect the updated verification and **Plan version**.
6. For configured AMD interpretation, choose **Describe a change with AMD**. Copy the displayed outage example: it uses a machine ID and dates from this loaded case. Select **Interpret planning request with AMD**, inspect the preview and receipt, then separately apply. A local clarification is labelled as local validation; a service error preserves the plan and offers retry. This step requires an actual API response, not a fabricated success.
7. In **Review & export**, select **Live AMD**, then **Explain this plan** if credentials are available. For an offline presentation, deliberately select **Mock demonstration (no API call)**; keep its label visible. Explain order 12 if desired. Expand evidence for exact statements, references, supporting passages and origin receipt.
8. Select **Save for supervisor review**, choose **Accepted for further review** or **Rejected**, and select **Record review decision**. Download **Download planner review package**. Pending is not acceptance; further-review acceptance is not production approval. The package includes the selected schedule, any verified baseline, changes, assumptions and matching review evidence.
9. Use **Reset to original scenario and reschedule** in the change tab. The previous explanation/review must be stale and cannot be reused as current acceptance. Sidebar settings retain the explicitly selected permissions; reset restores the original constraints of that configured case.

For a second run, explicitly enable the listed illustrative cleaning exemptions in sidebar **Orders, machines and cleaning rules**, then generate again. Only exact configured directed permissions can remove cleaning; colour alone cannot.

## Keep evidence types distinct

- **Published orders:** 35 real-origin Sitara records; recorded modelled resource values remain in unresolved source units.
- **Scheduling:** hypothetical virtual machines and assumed rules; CP-SAT and an independent verifier check this scenario, not factory readiness.
- **Synthetic monitoring:** separate 731-day thread-dyeing dataset, frozen CPU-trained models and frozen evaluation. Open it through sidebar **Workspace**.
- **Live AMD:** only an actual response receipt establishes live inference. The previous numeric-contract smoke check passed on 2026-10-15; this presentation update made no new live calls. Mock and previously generated responses remain labelled.

Factory calendars, capacities, recipe/quality compatibility, approved cleaning SOPs and production validation remain outstanding. No realised water/money savings, machine control or completed safety monitoring is claimed.

## Browser inspection and remaining checks

Real Microsoft Edge headless screenshots cover desktop and narrow setup, results,
machine timeline, Request a change and Review & export panels. The verification
report lists exact widths and outcomes. Native tab switching makes no inference
request. Automated tests separately cover previews, confirmation, reset, stale
reviews and exports. No new live AMD call was performed for this visual update.

Use Previous day / Next day to inspect the continuous daily calendar. The timeline
includes initial and terminal cleaning when they fall in the selected window.
Full-horizon blocks remain true to elapsed time; small blocks retain exact hover
details. Narrow layouts wrap cards and controls rather than squeezing their labels.
