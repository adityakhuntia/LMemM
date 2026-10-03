#!/usr/bin/env bash
# LMemM in the background. Same pipeline as `python3 lmemm.py`, detached.
#
#   ./run.sh start [N]  capture on app/tab change (+ every N s on the same window, default 5)
#   ./run.sh stop       stop, after resolving whatever is still queued
#   ./run.sh status     is it running, and how much have we got
#   ./run.sh log        follow the live one-line-per-frame output
#   ./run.sh pin        pin the current screen
#   ./run.sh memory     what was remembered
#
# Runs detached via nohup rather than a launchd agent on purpose: launched from
# your terminal, the process inherits your terminal's Screen Recording
# permission. A launchd agent is attributed to the python binary instead and
# silently captures wallpaper again.

set -u
cd "$(dirname "$0")"

PIDFILE=".lmemm.pid"
LOGFILE="lmemm.log"
PY="${PY:-python3}"

running() {
  [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null
}

case "${1:-status}" in

  start)
    if running; then
      echo "already running (pid $(cat $PIDFILE))"
      exit 0
    fi
    nohup "$PY" lmemm.py --every "${2:-5}" >> "$LOGFILE" 2>&1 &
    echo $! > "$PIDFILE"
    sleep 8
    if running; then
      echo "capturing + resolving in the background (pid $(cat $PIDFILE))"
      echo "you can close this terminal window. ./run.sh log to watch it."
      echo
      tail -n 4 "$LOGFILE"
    else
      echo "failed to start. last output:"
      echo
      tail -n 25 "$LOGFILE"
      rm -f "$PIDFILE"
      exit 1
    fi
    ;;

  stop)
    if running; then
      pid=$(cat "$PIDFILE")
      kill "$pid"
      # it resolves what's still queued and prints the session summary on the way out
      for _ in $(seq 1 120); do kill -0 "$pid" 2>/dev/null || break; sleep 0.5; done
      rm -f "$PIDFILE"
      sed -n '/^session /,$p' "$LOGFILE" | tail -n 30
    else
      echo "not running."
      rm -f "$PIDFILE"
    fi
    ;;

  status)
    if running; then
      echo "status   RUNNING (pid $(cat $PIDFILE))"
    else
      echo "status   stopped"
    fi
    n=$(ls -1 data/*.json 2>/dev/null | wc -l | tr -d ' ')
    r=$(ls -1 data/memory/*.json 2>/dev/null | wc -l | tr -d ' ')
    mb=$(du -sm data 2>/dev/null | cut -f1)
    echo "frames   ${n:-0}"
    echo "memories ${r:-0}"
    echo "disk     ${mb:-0} MB"
    if [ "${n:-0}" -gt 0 ]; then
      echo "latest   $(ls -1 data/*.json | tail -1 | xargs basename | sed 's/.json//')"
    fi
    ;;

  log)
    tail -f "$LOGFILE"
    ;;

  pin)
    "$PY" lmemm.py pin
    ;;

  memory)
    "$PY" lmemm.py memory "${2:-20}"
    ;;

  *)
    echo "usage: ./run.sh {start [seconds]|stop|status|log|pin|memory}"
    exit 1
    ;;
esac
