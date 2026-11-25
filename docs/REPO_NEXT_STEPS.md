# What to do in your AIORI GitHub repository after adding QoO-X

1. Keep the AIORI team-code repository name, collaboration, ownership and required files as instructed by AIORI. Do not create a replacement repo unless your mentor asks.
2. Add this project as a folder named `qoo-x/` (recommended) or merge its files into the repository carefully. Do not overwrite `Proposed-structure-hackathon.pdf`, the team's YouTube link or any required template files.
3. Commit with a clear message such as `Add QoO-X desktop experiment controller`.
4. Run tests from inside the add-on folder. If you named it `qoo-x`, use `cd qoo-x` first, then run `python -m compileall -q qoo_x qoo_x_app.py tests` and `python -m unittest discover -s tests -v`. If you put the files at the repository root, run those commands from the root. Fix any errors before pushing.
5. Push the changes to the AIORI team repo. Check that source files, README, tests and scenario configs appear online. The supplied team-repo bundle includes `.github/workflows/qoo-x-tests.yml` at the repository root, with its Python checks configured to run from `qoo-x/`. Keep that workflow file at the repository root. There is no `docs/team-repo-workflow.yml` in this bundle; do not look for or copy that nonexistent file.
6. Start the supplied QoO testbed separately. Follow its official routing instructions and confirm traffic crosses the gateway. Do not claim the app measured QoO just because its window opens.
7. Run one baseline DASH/TCP experiment first. In default Manual mode, apply the baseline in the supplied control panel and confirm that you have done so. Save its log and CSV row. Verify the actual QoO score and application-level metric in testbed telemetry.
8. Run the six scenarios for one application; then repeat the same conditions for the second mentor-approved application profile. Preserve raw logs and never delete failed runs.
9. Use `Results & Logs` to attach values read from actual testbed output/telemetry when the script does not print them. Check the units and write down where each metric came from.
10. Update `docs/results.md` in your team repo only after measured runs exist. Include experiment IDs, repeated-run information, limitations, and the dashboard/log evidence. Do not put illustrative/fake numbers in the results section.
11. Record the final screen demonstration showing a real condition change, real measured results, and the comparison under identical network conditions. Follow AIORI's current submission instructions for the video and any later working-demo link.

## Suggested commit sequence

- `Add QoO-X desktop controller and six scenario definitions`
- `Document testbed integration and field mapping`
- `Add measured baseline evidence and raw run logs`
- `Add six-scenario experiment dataset and comparison report`

The first two can be committed before the testbed works. The last two must wait for real experiments. The top-level `analysis/analyze_results.py` accepts both `profile_id` and QoO-X's `qoo_profile` column names and uses only Python's standard library.
