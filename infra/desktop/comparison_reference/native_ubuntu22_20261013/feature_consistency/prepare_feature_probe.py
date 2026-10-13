"""Extract ten unchanged EuRoC image pairs and original-parameter probe configs."""
from pathlib import Path
import re
import shutil
from PIL import Image
from rosbags.rosbag1 import Reader
from rosbags.typesys import Stores, get_typestore

repo = Path(__file__).resolve().parents[1]
output = repo.parent / 'results/ubuntu22-reproduction/feature-probe01'
output.mkdir(exist_ok=False)
store = get_typestore(Stores.ROS1_NOETIC)
pairs = {}
with Reader(repo.parent / 'data/euroc/MH_01_easy.bag') as reader:
    connections = [c for c in reader.connections if c.topic in ('/cam0/image_raw', '/cam1/image_raw')]
    for connection, _, raw in reader.messages(connections=connections):
        message = store.deserialize_ros1(raw, connection.msgtype)
        assert message.encoding == 'mono8' and message.step == message.width
        stamp = message.header.stamp.sec * 10**9 + message.header.stamp.nanosec
        camera = 0 if connection.topic == '/cam0/image_raw' else 1
        path = output / f'{stamp}_cam{camera}.png'
        Image.frombytes('L', (message.width, message.height), message.data.tobytes()).save(path)
        pairs.setdefault(stamp, {})[camera] = str(path.resolve())
        if len(pairs) == 10 and all(len(pair) == 2 for pair in pairs.values()):
            break
assert len(pairs) == 10 and all(len(pair) == 2 for pair in pairs.values())
(output / 'frames.txt').write_text(''.join(f'{stamp} {pair[0]} {pair[1]}\n' for stamp, pair in sorted(pairs.items())))
for mode in ('mono_imu', 'stereo_imu'):
    text = (repo / f'config/euroc/euroc_{mode}_config.yaml').read_text()
    text = re.sub(r'^output_path:.*$', f'output_path: "{output}"', text, flags=re.M)
    text = re.sub(r'^pose_graph_save_path:.*$', f'pose_graph_save_path: "{output}/pose_graph/"', text, flags=re.M)
    (output / f'euroc_{mode}_config.yaml').write_text(text)
for name in ('cam0_mei.yaml', 'cam1_mei.yaml'):
    shutil.copy2(repo / 'config/euroc' / name, output / name)
