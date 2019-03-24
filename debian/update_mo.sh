#!/bin/sh

cd po
for LANG in *
do
	echo "updating language file for ${LANG}"
	MDIR="../usr/share/locale/${LANG}/LC_MESSAGES/"
	mkdir -p ${MDIR}
	msgfmt -v -o ${MDIR}/lernstick-exam-client.mo ${LANG}/lernstick-exam-client.po
done
