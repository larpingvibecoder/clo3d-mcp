# Example prompts

Use a duplicate CLO project for live edits. Review screenshots after changes.

## First connection (read only)

> Call clo_status, then inspect scene_info if connected. Tell me the CLO build, current project, and pattern count. Do not change the scene.

## Offline drafting preview

> Use garment_plan_preview with use_scene_measurements=false for a knee-length A-line dress with a V neckline and short sleeves. Show the piece count and seam warnings. Do not build it.

## Build on a disposable project

> Inspect my loaded avatar and save a checkpoint called before_dress. Preview a knee-length A-line cotton dress using the scene measurements, then build it. Simulate and show front and back snapshots. Report the measurement source and any fit problems.

Example spec:

```json
{
  "garment": "dress",
  "silhouette": "a-line",
  "neckline": "v",
  "sleeve": "short",
  "length": "knee",
  "fabric": "cotton",
  "color": "#E8DFCE"
}
```

## Material edit

> Inspect the fabrics on my current garment. Save a checkpoint, then change the center fabric to an opaque cream cotton appearance. Check for an opacity map and show a new snapshot before deciding it is finished.

## Inspect a native function

> Find pattern_api.GetPatternCount with clo_api_catalog and read clo_api_describe. Call it and report the result. Do not invoke any other native function.

## Recovery

> A tool timed out. Inspect clo_status and the scene before retrying anything. Tell me whether the previous change appears to have happened and list the available checkpoints.
