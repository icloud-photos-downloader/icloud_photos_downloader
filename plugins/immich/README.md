# Immich Plugin for icloudpd

The Immich plugin integrates icloudpd with [Immich](https://immich.app), an open-source photo management solution. It automatically registers downloaded photos in Immich's external library, creates stacks for size variants, marks favorites, and organizes photos into albums.

## Features

- **Automatic Registration**: Photos are automatically registered in Immich after download via external library scanning
- **Size Variant Stacking**: Stack different size variants (original, adjusted, medium, etc.) together
- **Favorites Sync**: Synchronize iCloud favorites to Immich
- **Album Organization**: Organize photos into albums with flexible date-based rules
- **Live Photo Support**: Associate live photo videos with size variants
- **Batch Processing**: Process photos in batches to reduce server load
- **Favorites-Only Mode**: Lightweight mode to update favorites on existing downloaded images without full re-processing, as it's assumed you will add to favorites some time after you've taken the photos!
- **Directory Validation**: Ensures icloudpd directories are within Immich library import paths

## Requirements

- Immich server (tested with v1.100+)
- Immich API key (generate in Immich: Account Settings → API Keys)
- Immich external library with configured import paths
- icloudpd download directory must be within the Immich library's import paths

> **Note**: This plugin does NOT upload files - it uses Immich's external library feature to discover files already on disk.

## Quick Start

```bash
icloudpd \
  --directory /path/to/photos \
  --username me@you.com \
  --plugin immich \
  --immich-server-url http://localhost:2283 \
  --immich-api-key YOUR_API_KEY \
  --immich-library-id YOUR_LIBRARY_ID \
  --immich-stack-media \
  --immich-favorite adjusted
```

**Finding your Library ID:**

```bash
curl -H "x-api-key: YOUR_API_KEY" http://localhost:2283/api/libraries
```

Look for the `id` field of your external library in the JSON response.

## Configuration Parameters

### Required Parameters

- `--plugin immich` - Enable the Immich plugin
- `--immich-server-url URL` - Immich server URL (e.g., `http://localhost:2283`)
- `--immich-api-key KEY` - Immich API key
- `--immich-library-id ID` - Immich external library ID

### Core Features

#### Stacking Size Variants

Stack multiple size variants (original, adjusted, medium) together in Immich:

```bash
--immich-stack-media                    # Stack all downloaded sizes
--immich-stack-media adjusted,original  # Stack only these sizes (adjusted on top)
```

When enabled, the plugin creates stacks with the first specified size as the primary asset. For example, `--immich-stack-media adjusted,original` places the adjusted version on top of the stack.

#### Favoriting

Sync iCloud favorites to Immich:

```bash
--immich-favorite adjusted              # Mark adjusted size as favorite
--immich-favorite adjusted,medium       # Mark multiple sizes as favorite
--immich-favorite                       # Mark all sizes as favorite
```

The plugin reads the `isFavorite` flag from iCloud's PhotoAsset metadata and marks the specified sizes as favorites in Immich.

#### Albums

Organize photos into Immich albums with flexible rules:

```bash
--immich-album "iCloud Photos"                      # Add all sizes to one album
--immich-album "[adjusted]:iCloud"                  # Only adjusted size
--immich-album "[adjusted]:iCloud/{:%Y/%m}"         # Date-based albums
--immich-album "[medium]:iCloud JPG"                # Multiple rules
--immich-album "[original]:iCloud Raw"
```

Album template syntax:
- `[size1,size2]:template` - Only these sizes go to this album
- `template` - All sizes go to this album
- `{:%Y/%m}` - Date substitution using photo's creation date (supports strftime format codes)

Examples of date-based albums:
- `iCloud/{:%Y/%m}` → "iCloud/2024/01", "iCloud/2024/02", etc.
- `Photos/{:%Y}` → "Photos/2024", "Photos/2025", etc.

#### Live Photo Association

Associate live photo videos with size variants:

```bash
--associate-live-with-extra-sizes       # Associate live videos with all downloaded sizes
--associate-live-with-extra-sizes adjusted,medium # Associate live videos with adjusted and medium sizes
```

This ensures that when you have multiple size variants (e.g., medium and adjusted), the live photo video component is associated with all of them in Immich. Typically when downloading original size, the MOV of the live photo is named such that Immich automatically associates the MOV with the image then hides the MOV. This setting let's all sizes have the associated live mode.

### Processing Modes

#### Process Existing Files (`--immich-process-existing`)

Process files that icloudpd note are already exist on disk (not just newly downloaded), useful for adding existing photos to Immich when running icloudpd on your whole library. Also useful if you delete Immich albums and want to rebuild structure.

```bash
--immich-process-existing               # Full processing: stack, favorite, albums
```

**What it does:**
- Adds an 'already downloaded' assets to Immich
- Triggers library scan if assets missing
- Creates stacks for size variants
- Marks favorites based on `--immich-favorite`
- Adds to albums based on `--immich-album`
- Associates live photos

**Use case:** Initial setup or when you need full re-processing of existing files.

#### Process Existing Favorites Only (`--process-existing-favorites`)

Mark favorited images for existing downloaded photos. This is especially useful when combined with the `--until-found` flag as it allows for favoriting of images in iPhotos after they are taken and initially synced to Immich. Finding the _until found_ number that suits you is key:

```bash
--process-existing-favorites
```

**What it does:**
- Marks Favorites for existing images

**What it does NOT do:**
- Unmarks favorites

**Use case:** When running `icloudpd` with `--watch-with-interval` and `--until-found` for when favoriting in iPhotos is out of sync with taking of the images.

**Example scenarios:**

**Daily download with favorite updates on existing images:**
```bash
icloudpd \
  --directory /mnt/photos \
  --username user@icloud.com \
  --size original --size medium --size adjusted \
  --watch-with-interval 86400 \
  --until-found 1000 \
  --plugin immich \
  --immich-server-url https://immich.example.com \
  --immich-api-key YOUR_API_KEY \
  --immich-library-id abc123 \
   --immich-stack-media \
   --associate-live-with-extra-sizes \
  --immich-favorite adjusted \
  --process-existing-favorites \
  --immich-album [adjusted]:iCloud
```

This downloads and processes all new media - stacking (adjusted is primary), associating live will all sizes, favoriting the adjusted size, and placing the adjusted media in the `iCloud` album. If an existing media file is favorited since it was downloaded it will be added to Immich Favorites.

**Sync images and process existing files:**
This is useful if you are syncing your `icloudpd` downloads to Immich for the first time or need to otherwise re-process all media. NOTE: This will only process media that `icloudpd` can reach - for example if you have deleted media off iCloud then `icloudpd` will not see it, and hence the _process existing_ will not work on those files.
```bash
# One-time full sync
icloudpd \
  --directory /mnt/photos \
  --username user@icloud.com \
  --size original --size medium --size adjusted \
  --plugin immich \
  --immich-server-url https://immich.example.com \
  --immich-api-key YOUR_API_KEY \
  --immich-library-id abc123 \
   --immich-stack-media \
   --associate-live-with-extra-sizes \
  --immich-favorite adjusted \
  --immich-album [adjusted]:iCloud
  --immich-process-existing \
```

This checks ALL photos in your iCloud library, processes only existing files that are favorites, and marks the adjusted size as favorite in Immich.

### Batch Processing

Batch processing reduces load on your Immich server by accumulating photos before processing them, triggering the resource-intensive library scan operation less frequently.

**Problem solved:** When processing many photos, each photo triggers an Immich library scan. This can overwhelm the Immich server, causing OOM (out of memory) errors.

**Solution:** Accumulate photos into batches and trigger library scan once per batch instead of once per photo.

#### Configuration

```bash
--immich-batch-process 10               # Process every 10 photos
--immich-batch-process all              # Process all at end of run
--immich-batch-process                  # Process all at end of run
--immich-batch-log-file /path/file.json # (Optional) Custom log file (default: ~/.pyicloud/immich_pending_files.json)
```

**Options:**
- **No argument or `all`**: Process all photos at end of run
- **Integer N**: Process every N photos (e.g., `10` = process batch after every 10 photos)
- **Default**: Disabled (process each photo immediately, equivalent to batch size 1)

#### Benefits

- **Reduced Server Load**: Fewer library scans = less memory and CPU usage
- **Crash Recovery**: Persistent log file allows recovery from interruptions
- **Flexible Batching**: Process every N photos or all at end
- **Same Functionality**: Stacking, favoriting, and albums work identically

#### Crash Recovery

The batch log file (`~/.pyicloud/immich_pending_files.json` by default) tracks unprocessed photos.

**How it works:**

1. **During Run**: Each photo is added to batch queue and saved to log file
2. **After Processing**: Successfully processed photos are removed from log file
3. **On Crash**: Log file retains unprocessed photos
4. **Next Run**: Plugin loads pending photos from log file and processes them first

**Example scenario:**

```bash
# Start processing 1000 photos with batch size 50
icloudpd ... --immich-batch-process 50

# Progress:
# Batch 1 (photos 1-50) → Processed ✓ → Removed from log
# Batch 2 (photos 51-100) → Processed ✓ → Removed from log
# Batch 3 (photos 101-150) → CRASH! → Still in log file

# Next run automatically recovers:
# → Loads photos 101-150 from log file
# → Processes them first
# → Continues with new photos
```

**Manual recovery:**

If needed, you can inspect or clear the log file:

```bash
# View pending photos
cat ~/.pyicloud/immich_pending_files.json

# Clear pending photos (start fresh)
rm ~/.pyicloud/immich_pending_files.json
```

**Best practices:**

1. **Start Small**: Try batch size 10-20 for your first run
2. **Monitor Immich**: Watch memory/CPU usage during library scan
3. **Adjust**: Decrease batch size if server handles it well, increase if OOM errors occur

### Performance Tuning

```bash
--immich-scan-timeout 60.0              # Wait up to 60s for library scan (default: 5s)
--immich-poll-interval 1.0              # Check every 1s during scan wait (default: 1s)
```

- `--immich-scan-timeout`: Maximum time to wait for Immich to scan and register files. Use `0` for infinite wait. Increase if your Immich server is slow.
- `--immich-poll-interval`: How frequently to check if assets are registered during scan wait. Lower values = more responsive, but more API calls.

## Real-World Example

Complete setup for continuous sync with Immich integration:

```bash
icloudpd \
  --directory /path/to/iCloud \
  --cookie-directory /home/user/.pyicloud \
  --username me@you.com \
  --folder-structure none \
  --set-exif-datetime \
  --watch-with-interval 86400 \
  --until-found 1000 \
  --keep-unicode-in-filenames \
  --file-match-policy name-id7 \
  --size original --size medium --size adjusted \
  --log-level debug \
  --xmp-sidecar \
  --favorite-to-rating 1 \
  --plugin immich \
  --immich-server-url http://localhost:2283 \
  --immich-api-key "XYZ" \
  --immich-library-id "ABC" \
  --immich-stack-media \
  --immich-favorite adjusted \
  --process-existing-favorites \
  --associate-live-with-extra-sizes \
  --immich-scan-timeout 60.0 \
  --immich-poll-interval 1.0 \
  --immich-batch-process 10 \
  --immich-album "[adjusted]:iCloud" \
  --immich-album "[medium]:iCloud JPG" \
  --immich-album "[original]:iCloud Raw"
```

This configuration:
- Downloads 3 sizes (original, medium, adjusted)
- Runs daily via `--watch-with-interval 86400`
- Processes up to 1000 existing photos per run (`--until-found 1000`)
- Updates favorites for existing photos (`--process-existing-favorites`)
- Batches every 10 photos to reduce server load
- Stacks all size variants together
- Marks adjusted size as favorite in Immich
- Organizes into 3 albums by size type

## How It Works

This plugin uses Immich's **external library** feature - it does not upload files. Instead:

1. **Download**: icloudpd downloads photos to a directory within Immich's library import paths
2. **Trigger Scan**: Plugin triggers an Immich external library scan to discover new files
3. **Wait for Assets**: Polls Immich API until all downloaded files are registered as assets
4. **Stack**: If enabled, stacks size variants together using Immich's stack API
5. **Associate Live Photos**: Links live photo videos to images
6. **Mark Favorites**: Syncs favorite status from iCloud to Immich
7. **Organize Albums**: Adds photos to albums based on configured rules

## Directory Validation

The plugin validates that all icloudpd download directories are within Immich library import paths. If validation fails, icloudpd will exit with an error message showing which directories are invalid.

To fix validation errors:
1. Check your Immich library's import paths (Settings → Libraries)
2. Ensure icloudpd download directory is a subdirectory of an import path
3. Date templates (e.g., `%Y/%m`) are stripped before validation

Example:
```bash
# Immich import path: /mnt/photos
# icloudpd directory: /mnt/photos/icloud  ✓ Valid
# icloudpd directory: /home/user/downloads  ✗ Invalid
```

## Version

1.0.0

## License

MIT
