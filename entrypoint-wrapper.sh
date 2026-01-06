#!/bin/sh
# Wrapper script to convert environment variables to icloudpd command line arguments

ARGS=""

# Username (required)
if [ -n "$apple_id" ]; then
    ARGS="$ARGS --username $apple_id"
elif [ -n "$APPLE_ID" ]; then
    ARGS="$ARGS --username $APPLE_ID"
fi

# Directory (required)
if [ -n "$download_path" ]; then
    ARGS="$ARGS --directory $download_path"
elif [ -n "$DOWNLOAD_PATH" ]; then
    ARGS="$ARGS --directory $DOWNLOAD_PATH"
fi

# Watch interval
if [ -n "$synchronisation_interval" ]; then
    ARGS="$ARGS --watch-with-interval $synchronisation_interval"
elif [ -n "$SYNCHRONISATION_INTERVAL" ]; then
    ARGS="$ARGS --watch-with-interval $SYNCHRONISATION_INTERVAL"
fi

# Folder structure
if [ -n "$folder_structure" ]; then
    ARGS="$ARGS --folder-structure \"$folder_structure\""
elif [ -n "$FOLDER_STRUCTURE" ]; then
    ARGS="$ARGS --folder-structure \"$FOLDER_STRUCTURE\""
fi

# Cookie directory (default to /config if mounted)
if [ -n "$cookie_directory" ]; then
    ARGS="$ARGS --cookie-directory $cookie_directory"
elif [ -n "$COOKIE_DIRECTORY" ]; then
    ARGS="$ARGS --cookie-directory $COOKIE_DIRECTORY"
elif [ -d "/config" ]; then
    ARGS="$ARGS --cookie-directory /config"
fi

# Boolean flags
# Nota: --skip-check y --delete-empty-directories no existen en el repositorio oficial
# --skip-album tampoco existe, pero podemos usar --album para especificar qué descargar

[ "$auto_delete" = "true" ] && ARGS="$ARGS --auto-delete" || true
[ "$AUTO_DELETE" = "true" ] && ARGS="$ARGS --auto-delete" || true

# convert_heic_to_jpeg no está disponible en el repositorio oficial

[ "$skip_videos" = "true" ] && ARGS="$ARGS --skip-videos" || true
[ "$SKIP_VIDEOS" = "true" ] && ARGS="$ARGS --skip-videos" || true

[ "$skip_live_photos" = "true" ] && ARGS="$ARGS --skip-live-photos" || true
[ "$SKIP_LIVE_PHOTOS" = "true" ] && ARGS="$ARGS --skip-live-photos" || true

[ "$set_exif_datetime" = "true" ] && ARGS="$ARGS --set-exif-datetime" || true
[ "$SET_EXIF_DATETIME" = "true" ] && ARGS="$ARGS --set-exif-datetime" || true

[ "$keep_unicode" = "true" ] && ARGS="$ARGS --keep-unicode-in-filenames" || true
[ "$KEEP_UNICODE" = "true" ] && ARGS="$ARGS --keep-unicode-in-filenames" || true

# Album (para especificar qué descargar, no para saltar)
if [ -n "$photo_album" ]; then
    ARGS="$ARGS --album $photo_album"
elif [ -n "$PHOTO_ALBUM" ]; then
    ARGS="$ARGS --album $PHOTO_ALBUM"
fi

# Photo size
if [ -n "$photo_size" ]; then
    ARGS="$ARGS --size $photo_size"
elif [ -n "$PHOTO_SIZE" ]; then
    ARGS="$ARGS --size $PHOTO_SIZE"
fi

# Live photo size
if [ -n "$live_photo_size" ]; then
    ARGS="$ARGS --live-photo-size $live_photo_size"
elif [ -n "$LIVE_PHOTO_SIZE" ]; then
    ARGS="$ARGS --live-photo-size $LIVE_PHOTO_SIZE"
fi

# Recent photos
if [ -n "$recent_only" ] && [ "$recent_only" != "0" ]; then
    ARGS="$ARGS --recent $recent_only"
elif [ -n "$RECENT_ONLY" ] && [ "$RECENT_ONLY" != "0" ]; then
    ARGS="$ARGS --recent $RECENT_ONLY"
fi

# Library
if [ -n "$photo_library" ]; then
    ARGS="$ARGS --library $photo_library"
elif [ -n "$PHOTO_LIBRARY" ]; then
    ARGS="$ARGS --library $PHOTO_LIBRARY"
fi

# Log level
if [ -n "$debug_logging" ] && [ "$debug_logging" = "true" ]; then
    ARGS="$ARGS --log-level debug"
elif [ -n "$DEBUG_LOGGING" ] && [ "$DEBUG_LOGGING" = "true" ]; then
    ARGS="$ARGS --log-level debug"
fi

# Password (if provided)
if [ -n "$password" ]; then
    ARGS="$ARGS --password \"$password\""
elif [ -n "$PASSWORD" ]; then
    ARGS="$ARGS --password \"$PASSWORD\""
fi

# Auth only mode
[ "$auth_only" = "true" ] && ARGS="$ARGS --auth-only" || true
[ "$AUTH_ONLY" = "true" ] && ARGS="$ARGS --auth-only" || true

# If no arguments were provided, show help
if [ -z "$ARGS" ] && [ "$1" != "icloudpd" ] && [ "$1" != "icloud" ]; then
    exec /app/icloudpd --help
    exit 0
fi

# If first argument is 'icloud' or 'icloudpd', use it, otherwise default to icloudpd
if [ "$1" = "icloud" ] || [ "$1" = "icloudpd" ]; then
    CMD="$1"
    shift
    # Combine remaining args with our generated args
    exec /app/$CMD $ARGS "$@"
else
    # Default to icloudpd with our generated args
    exec /app/icloudpd $ARGS "$@"
fi

