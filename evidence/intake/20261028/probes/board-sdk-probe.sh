set +e
work=$(mktemp -d /tmp/vins-intake-sdk-XXXXXX)
printf 'probe_directory=%s\n' "$work"
cd "$work" || exit 1
printf '\n[ENUMERATION]\n'
timeout 12 /opt/spinnaker/bin/Enumeration < /dev/null > enumeration.log 2>&1
printf 'enumeration_exit=%s\n' "$?"
cat enumeration.log
printf '\n[ACQUISITION]\n'
timeout -k 3 20 /opt/spinnaker/bin/Acquisition < /dev/null > acquisition.log 2>&1
printf 'acquisition_exit=%s\n' "$?"
cat acquisition.log
printf '\n[IMAGE FILES]\n'
find "$work" -maxdepth 1 -type f -printf '%s %f\n'
printf '\n[IMAGE CONTENT]\n'
python3 - <<'PY'
import glob,json
import cv2
images=[]
for f in glob.glob('*.jpg'):
 a=cv2.imread(f,cv2.IMREAD_UNCHANGED)
 images.append({'file':f,'shape':list(a.shape) if a is not None else None,'min':int(a.min()) if a is not None else None,'max':int(a.max()) if a is not None else None,'mean':float(a.mean()) if a is not None else None,'std':float(a.std()) if a is not None else None})
print(json.dumps(images,indent=2))
PY
