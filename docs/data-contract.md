# Workout and analytics contracts

- Session filenames: `YYYY-MM-DD Workout A.md` or `... B.md`; dates must be valid ISO
  local calendar dates. Archive subdirectories are included. The historical TSV is
  excluded because it does not establish A/B identity.
- Canonical templates: `_workout-a.md` / `_workout-b.md`; numeric rows are
  `exercise name weight reps`. Exercise identity collapses whitespace and case.
- Weight is nonnegative external **lb**, up to four decimal places; repetitions
  are nonnegative integers. A zero external load is valid, not missing data.
- Physical therapy is an activity with one session row per muscle/area. Each row's
  `activity_area` is optional single-line text of at most 500 characters, with its
  own removal/restore state. `therapy_areas` summarizes included labeled rows for
  older API clients; older combined fields are split without inventing completion.
  Historical mention alone has unknown completion and no invented weight/reps.
  Areas autosave, roundtrip through note metadata, and default from the latest
  completed session or optional local configuration. Existing history is not inferred.
  Therapy labels stay outside the analytics snapshot; numeric metrics are unchanged.
- Workout status: draft, finalizing, completed, discarded, or review. Only
  completed sessions advance A/B and enter workout facts. Set status: pending,
  performed, skipped, removed, or unknown. Only performed numeric sets enter set facts.
  Cancelling an unfinished draft sets `discarded`, with revision protection and
  no completed-note publication or A/B advancement. Completed/finalizing workouts
  cannot be cancelled through this action.
- Stable session/set IDs and planned positions preserve ordering. Full-form updates
  require the current revision and exactly the session's own set IDs. Stale updates
  are rejected; finishing includes the latest input state.
- Added session rows have new IDs, appended positions, increasing exercise
  occurrence numbers, and no template key. Numeric additions copy the latest
  included set's weight/reps and remain session-only. Exercise cards group additions
  with their existing exercise. Note export/import retains these unplanned rows.
- App-written notes retain `session_id`, completion status, lb, notes, therapy areas, and ordered
  `gym_sets` mapping in YAML frontmatter. Plain result rows contain performed sets
  only. Metadata/results disagreement is an external-edit conflict.
  Completion time records the Finish action; completion status waits for note
  publication. Note text is serialized so the existing permissive Templater cannot
  mistake reminders ending in numbers for exercise sets.
- Imports retain original text, path, checksum, batch, and parsing issues locally.
  Unchanged sources are idempotent; changed sources require reconciliation.
- Operational and warehouse schemas must match the declared snapshot contract.
  Every raw warehouse row carries snapshot ID and extraction timestamp. Only a
  fully manifested snapshot is eligible for transformations.
- The dashboard reads operational recordings directly. Its selected date range
  is inclusive, through the configured local current date. Sessions and training
  days use completed sessions; exercise sets, reps, and load volume use performed
  numeric rows only. Top-set weight is paired with the reps of the same recorded
  set, taking more reps on equal weight. Changes compare earliest/latest sessions
  in the range; one session has no comparison. Weekly buckets begin on Monday
  and show at most the latest 12 weeks. Unperformed/absent exercises are not
  converted to zero-valued exercise observations.

## Model grain and metrics

Staging: one session, exercise, or planned set in the latest manifested snapshot.
`int_completed_workout_sets` / `fct_workout_sets`: one performed numeric set from a
completed session. `int_session_exercise_metrics`: one completed session × exercise.
`dim_exercises`: one exercise/activity identity. `fct_workout_sessions`: one completed
session, including activity-only sessions with zero numeric totals.

`session_position` preserves legacy recorded order or app planned order, including
removed gaps. `template_key` is nullable: unknown legacy planned correspondence is
not invented, even when latest values are reused in order for a new draft's defaults.

Recorded load-volume = external weight in lb × performed reps. Sum only numeric
performed sets. It does not quantify bodyweight work, physical therapy effort, or
training effectiveness. Weekly session counts measure recording activity; no fixed
schedule or adherence target is inferred. No duration is derived from imported dates.

Keys, relationships, statuses, completed/performed filtering, arithmetic, row-count
conservation, and aggregation grain are verified with dbt generic and singular tests.
