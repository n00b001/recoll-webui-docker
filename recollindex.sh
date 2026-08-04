#!/bin/sh

set -u

CONTAINER="recoll-engine"

LOG="/mnt/shuttle/share/app-data/recoll/.recoll/recollindex.log"
CONFIG="/mnt/shuttle/share/app-data/recoll/.recoll/recoll.conf"
INDEX_PATH="/root/.recoll/xapiandb"
LOCK="/tmp/recollindex-wrapper.lock"

REBUILD=false


if [ "${1:-}" = "--rebuild" ]; then
    REBUILD=true
fi


timestamp()
{
    date "+%Y-%m-%d %H:%M:%S"
}


print_section()
{
    echo
    echo "####################################################################"
    echo "$1"
    echo "####################################################################"
}


run_timed()
{
    LABEL="$1"
    shift

    START=$(date +%s)

    echo
    echo "[$(timestamp)] START: $LABEL"

    "$@"

    EXIT_CODE=$?

    END=$(date +%s)
    DURATION=$((END - START))

    echo "[$(timestamp)] END: $LABEL"
    echo "Duration: ${DURATION}s"
    echo "Exit code: $EXIT_CODE"

    return "$EXIT_CODE"
}


storage_diagnostics()
{
    echo
    echo "Storage diagnostics"
    echo "-------------------"

    echo
    echo "NOTE:"
    echo "zpool/zfs diagnostics intentionally run on TrueNAS host."
    echo "They are NOT executed inside the Recoll container."

    echo
    echo "ZFS pools:"
    zpool status || true


    echo
    echo "Selected ZFS datasets:"
    zfs list \
        -o NAME,USED,AVAIL,REFER,MOUNTPOINT \
        | awk '
            NR == 1 ||
            $1 == "lambo/share" ||
            $1 == "shuttle/share"
        ' \
        || true


    echo
    echo "ZFS ARC:"
    if [ -f /proc/spl/kstat/zfs/arcstats ]; then
        grep -E \
            "^(size|c_min|c_max|hits|misses)" \
            /proc/spl/kstat/zfs/arcstats \
            || true
    else
        echo "ARC stats unavailable"
    fi


    echo
    echo "Filesystem usage:"
    df -h \
        /mnt/shuttle/share \
        /mnt/lambo/share \
        2>/dev/null \
        || true


    echo
    echo "Block devices:"
    lsblk \
        -o NAME,SIZE,MODEL,SERIAL,FSTYPE,MOUNTPOINT \
        || true


    echo
    echo "PCI storage adapters:"
    lspci \
        | grep -Ei \
            "sata|ahci|raid|sas|lsi|marvell|asm|asmedia|usb" \
        || true


    echo
    echo "SMART devices:"
    smartctl --scan-open \
        || true


    echo
    echo "Recent kernel storage messages:"
    dmesg \
        | grep -Ei \
            "ata|ahci|sas|scsi|usb|reset|timeout|error|failed|link|crc" \
        | tail -100 \
        || true
}


container_diagnostics()
{
    echo
    echo "Container diagnostics"
    echo "---------------------"


    echo
    echo "Container status:"
    docker ps \
        --filter "name=$CONTAINER" \
        --format \
        "table {{.Names}}\t{{.Status}}\t{{.Image}}" \
        || true


    echo
    echo "Container image:"
    docker inspect "$CONTAINER" \
        --format \
        "{{.Config.Image}}" \
        || true


    echo
    echo "Recoll version:"
    docker exec "$CONTAINER" \
        sh -c \
        "recollindex -h 2>&1 | head -3" \
        || true


    echo
    echo "Index size:"
    docker exec "$CONTAINER" \
        du -sh "$INDEX_PATH" \
        2>/dev/null \
        || true


    echo
    echo "Container resources:"
    docker stats "$CONTAINER" \
        --no-stream \
        || true


    echo
    echo "Existing Recoll processes:"
    docker exec "$CONTAINER" \
        sh -c \
        "ps -eo pid,comm,args | grep -E 'recoll(index)?|rcl' | grep -v grep" \
        || true
}


check_existing_indexers()
{
    echo
    echo "Checking existing Recoll indexers..."

    RUNNING_INDEXERS=$(docker exec "$CONTAINER" \
        sh -c \
        "pgrep -x recollindex | wc -l" \
        2>/dev/null \
        || echo 0)


    echo "Existing recollindex processes: $RUNNING_INDEXERS"


    if [ "$RUNNING_INDEXERS" -gt 0 ]; then
        echo
        echo "ERROR: recollindex already running."
        echo "Refusing to start another indexer."
        return 1
    fi


    return 0
}

if [ "$REBUILD" = true ]; then

    echo
    echo "WARNING: This will completely rebuild the Recoll index."
    echo "This may take a long time."
    printf "Continue? [y/N] "

    read -r CONFIRMATION

    case "$CONFIRMATION" in
        y|Y|yes|YES)
            echo "Starting full rebuild..."
            ;;
        *)
            echo "Cancelled."
            exit 0
            ;;
    esac

fi


(
    flock -n 9 || {
        echo "ERROR: Another Recoll wrapper process is already running."
        exit 1
    }


    START_TIME=$(date +%s)
    START_PID=$$


    {
        print_section "START"

        echo "PID       : $START_PID"
        echo "Hostname  : $(hostname)"
        echo "User      : $(whoami)"
        echo "Arguments : $*"
        echo "Time      : $(date)"
        echo "Container : $CONTAINER"


        run_timed \
            "Initial container diagnostics" \
            container_diagnostics


        run_timed \
            "Initial storage diagnostics" \
            storage_diagnostics


        echo
        echo "Configuration"
        echo "-------------"

        if [ -f "$CONFIG" ]; then
            grep -E \
                '^(topdirs|dbdir|indexstemminglanguages|indexallfilenames|loglevel|maxfsmbexp|storeAllExtraDbFields|usesystemhacks)' \
                "$CONFIG" \
                || true
        else
            echo "Missing config file: $CONFIG"
        fi


        if ! check_existing_indexers; then

            echo
            echo "Aborting because Recoll is already indexing."

            END_TIME=$(date +%s)
            DURATION=$((END_TIME - START_TIME))

            echo
            echo "--------------------------------------------------------------------"
            echo "Exit code : 2"
            echo "Duration  : ${DURATION}s"
            echo "Finished  : $(date)"

            print_section "END"

            echo "PID       : $START_PID"
            echo "Exit code : 2"
            echo "Time      : $(date)"

            exit 2
        fi


        echo
        echo "Running indexing..."
        echo "-------------------"


        if [ "$REBUILD" = true ]; then

            echo "Mode: FULL REBUILD"
            echo "Command:"
            echo "recollindex -z"

            docker exec "$CONTAINER" \
                sh -c \
                "ionice -c 3 nice -n 19 recollindex -z"

        else

            echo "Mode: INCREMENTAL"
            echo "Command:"
            echo "recollindex"

            docker exec "$CONTAINER" \
                sh -c \
                "ionice -c 3 nice -n 19 recollindex"

        fi


        INDEX_EXIT_CODE=$?


        run_timed \
            "Post-index container diagnostics" \
            container_diagnostics


        run_timed \
            "Post-index storage diagnostics" \
            storage_diagnostics


        END_TIME=$(date +%s)

        DURATION=$((END_TIME - START_TIME))

        HOURS=$((DURATION / 3600))
        MINUTES=$(((DURATION % 3600) / 60))
        SECONDS=$((DURATION % 60))


        echo
        echo "--------------------------------------------------------------------"

        echo "Exit code : $INDEX_EXIT_CODE"

        printf "Duration  : %02dh %02dm %02ds\n" \
            "$HOURS" \
            "$MINUTES" \
            "$SECONDS"

        echo "Finished  : $(date)"


        print_section "END"

        echo "PID       : $START_PID"
        echo "Exit code : $INDEX_EXIT_CODE"
        echo "Time      : $(date)"


        exit "$INDEX_EXIT_CODE"


    } >> "$LOG" 2>&1


) 9>"$LOCK"
