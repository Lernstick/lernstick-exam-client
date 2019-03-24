xgettext -L Shell --from-code UTF-8 --add-comments=## usr/bin/*
sed -i "s/charset=CHARSET/charset=UTF-8/g" messages.po
cd po; for i in *; do cd $i; msgmerge -U lernstick-exam-client.po ../../messages.po; cd ..; done; cd ..
vi po/*/lernstick-exam-client.po
