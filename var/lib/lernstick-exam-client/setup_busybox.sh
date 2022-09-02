#!/bin/bash

DESTDIR="$1"
verbose="y"

# create directories
for d in etc bin sbin proc ; do
  mkdir "$DESTDIR/$d" || true 2>/dev/null
done

# copy busybox and dependencies to /run/initramfs
# Bug is filed: https://bugs.debian.org/cgi-bin/bugreport.cgi?bug=953563
# see /usr/share/initramfs-tools/hooks/zz-busybox
BB_BIN=/bin/busybox

if [ -r /usr/share/initramfs-tools/hook-functions ]; then
  . /usr/share/initramfs-tools/hook-functions

  if [ -f $DESTDIR/bin/sh ] && cmp -s $DESTDIR/bin/sh $BB_BIN ; then
    # initramfs copies busybox into /bin/sh, undo this
    rm -f $DESTDIR/bin/sh
  fi
  rm -f $DESTDIR/bin/busybox      # for compatibility with old initramfs
  copy_exec $BB_BIN /bin/busybox

  # this line fixes the canonicalization problem: copy_file copies the binary
  # to /usr/bin instead of /bin, causing the rest of the script to fail, specially
  # the line that link the alias to busybox below
  ln "$DESTDIR/usr/bin/busybox" "$DESTDIR/bin/busybox"

  for alias in $($BB_BIN --list-long); do
    alias="${alias#/}"
    case "$alias" in
      # strip leading /usr, we don't use it
      usr/*) alias="${alias#usr/}" ;;
      */*) ;;
      *) alias="bin/$alias" ;;  # make it into /bin
    esac

    [ -e "$DESTDIR/$alias" ] || \
      ln "$DESTDIR/bin/busybox" "$DESTDIR/$alias"
  done

  # copy plymouth
  . /usr/share/initramfs-tools/hooks/plymouth

  # copy systemctl needed for final shutdown
  copy_exec /bin/systemctl

  # disable set -e again (set in /usr/share/initramfs-tools/hooks/plymouth)
  set +e

fi
