import os
from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    IncludeLaunchDescription,
    ExecuteProcess,
    RegisterEventHandler,
    TimerAction,
)
from launch.event_handlers import OnProcessExit
from launch_ros.actions import Node
from launch.substitutions import TextSubstitution, LaunchConfiguration
from launch.launch_description_sources import PythonLaunchDescriptionSource
from ament_index_python import get_package_share_directory, get_package_prefix

# ─────────────────────────────────────────────────────────────────────
# 竞速模式开关
#   RACE_MODE=true  → 关闭编码器+WebSocket+rosbridge (VPU 只给解码器用)
#   RACE_MODE=false → 全部启动 (默认，调试/开发用)
# ─────────────────────────────────────────────────────────────────────
_RACE_MODE = os.getenv('RACE_MODE', 'false')
_IS_RACE = _RACE_MODE.lower() == 'true'
if _IS_RACE:
    print("[launch] ★ RACE MODE: 关闭编码器/WebSocket/rosbridge，VPU 仅用于解码")
else:
    print("[launch] Debug mode: 全部启动 (编码器+WebSocket+rosbridge)")

def generate_launch_description():
    # Copy config files
    dnn_node_example_path = os.path.join(get_package_prefix('dnn_node_example'), "lib/dnn_node_example")
    os.system(f"cp -r {dnn_node_example_path}/config .")

    # Declare launch arguments
    launch_args = [
        DeclareLaunchArgument("dnn_example_config_file", default_value=TextSubstitution(text="config/fcosworkconfig.json")),
        DeclareLaunchArgument("dnn_example_dump_render_img", default_value=TextSubstitution(text="0")),
        DeclareLaunchArgument("dnn_example_image_width", default_value=TextSubstitution(text="480")),
        DeclareLaunchArgument("dnn_example_image_height", default_value=TextSubstitution(text="272")),
        DeclareLaunchArgument("dnn_example_msg_pub_topic_name", default_value=TextSubstitution(text="hobot_dnn_detection")),
        DeclareLaunchArgument('device', default_value='/dev/video0', description='usb camera device'),
        DeclareLaunchArgument(
            'camera_pipeline_delay', default_value='1.0',
            description='Seconds to wait after camera configuration before starting the camera pipeline'),
        DeclareLaunchArgument(
            'vision_start_delay', default_value='4.0',
            description='Seconds to wait after camera configuration before starting vision and websocket nodes'),
    ]

    # ★ 启动前锁死摄像头参数：防止光线变化时自动切分辨率导致崩溃
    lock_camera = ExecuteProcess(
        cmd=[
            'bash', '-c',
            'for dev in /dev/video0 /dev/video1; do '
            '[ -e "$dev" ] || continue; '
            'v4l2-ctl -d "$dev" -c exposure_dynamic_framerate=0 2>/dev/null; '
            'v4l2-ctl -d "$dev" --set-fmt-video=width=640,height=480,pixelformat=MJPG 2>/dev/null && '
            'echo "摄像头已锁死: $dev 640x480 MJPG" && exit 0; '
            'done; '
            'echo "警告: 未找到 MJPG 摄像头"'
        ],
        output='screen'
    )

    rosbridge_node = ExecuteProcess(
        cmd=['ros2', 'launch', 'rosbridge_server', 'rosbridge_websocket_launch.xml'],
        output='screen'
    )

    # Include launch descriptions
    usb_node = IncludeLaunchDescription(PythonLaunchDescriptionSource(get_package_share_directory('hobot_usb_cam') + '/launch/hobot_usb_cam.launch.py'),
                                       launch_arguments={'usb_image_width': '640', 'usb_image_height': '480',
                                                         'usb_pixel_format': 'mjpeg',
                                                         'usb_zero_copy': 'True',
                                                         'usb_video_device': LaunchConfiguration('device')}.items())

    nv12_decode_node = IncludeLaunchDescription(PythonLaunchDescriptionSource(get_package_share_directory('hobot_codec') + '/launch/hobot_codec_decode.launch.py'),
                                               launch_arguments={'codec_channel'  : '1',
                                                                 'codec_in_format':'jpeg',        'codec_out_format': 'nv12',
                                                                 'codec_in_mode'  : 'shared_mem', 'codec_out_mode'  : 'shared_mem',
                                                                 'codec_sub_topic': '/hbmem_img', 'codec_pub_topic' : '/nv12_img'}.items())

    img_encode_node = IncludeLaunchDescription(PythonLaunchDescriptionSource(get_package_share_directory('hobot_codec') + '/launch/hobot_codec_encode.launch.py'),
                                               launch_arguments={'codec_channel'  : '2',             'codec_jpg_quality': '70.0',  'codec_output_framerate' : '30',
                                                                 'codec_in_format': 'nv12',          'codec_out_format' : 'jpeg',
                                                                 'codec_in_mode'  : 'shared_mem',    'codec_out_mode'   : 'ros',
                                                                 'codec_sub_topic': '/nv12_img', 'codec_pub_topic'  : '/jpeg_img'}.items())
                                                                 
    web_node = IncludeLaunchDescription(PythonLaunchDescriptionSource(get_package_share_directory('websocket') + '/launch/websocket.launch.py'),
                                        launch_arguments={'websocket_image_topic': '/jpeg_img', 'websocket_image_type': 'mjpeg', # racing_obstacle_detection
                                                          'websocket_smart_topic': '/racing_track_center_detection_n'}.items())    # racing_track_center_detection

    racing_track_detection_resnet_go = IncludeLaunchDescription(PythonLaunchDescriptionSource(
                                        get_package_share_directory('racing_track_detection_resnet_go') + '/launch/racing_track_detection_resnet.launch.py'))

    racing_track_detection_resnet_s = IncludeLaunchDescription(PythonLaunchDescriptionSource(
                                        get_package_share_directory('racing_track_detection_resnet_s') + '/launch/racing_track_detection_resnet.launch.py'))

    racing_track_detection_resnet_n = IncludeLaunchDescription(PythonLaunchDescriptionSource(
                                        get_package_share_directory('racing_track_detection_resnet_n') + '/launch/racing_track_detection_resnet.launch.py'))

    racing_track_detection_resnet_back = IncludeLaunchDescription(PythonLaunchDescriptionSource(
                                        get_package_share_directory('racing_track_detection_resnet_back') + '/launch/racing_track_detection_resnet.launch.py'))


    racing_obstacle_detection_yolo = IncludeLaunchDescription(PythonLaunchDescriptionSource(
                                        get_package_share_directory('racing_obstacle_detection_yolo') + '/launch/racing_obstacle_detection_yolo.launch.py'))

    origincar_base = IncludeLaunchDescription(PythonLaunchDescriptionSource(
                                        get_package_share_directory('origincar_base') + '/launch/origincar_bringup.launch.py'))
    
    racing_control = IncludeLaunchDescription(PythonLaunchDescriptionSource(
                                        get_package_share_directory('racing_control') + '/launch/racing_control.launch.py'))
    # Algorithm node
    dnn_node_example_node = Node(
        package='dnn_node_example',
        executable='example',
        output='screen',
        parameters=[
            {"config_file": LaunchConfiguration('dnn_example_config_file')},
            {"dump_render_img": LaunchConfiguration('dnn_example_dump_render_img')},
            {"feed_type": 1},
            {"is_shared_mem_sub": 1},
            {"msg_pub_topic_name": LaunchConfiguration("dnn_example_msg_pub_topic_name")}
        ],
        arguments=['--ros-args', '--log-level', 'warn']
    )

    vision_language_model = Node(
        package='vision_language_model',
        executable='vision_language_model',
        output='screen',
        arguments=['--ros-args', '--log-level', 'info']
    )

    qrcode = Node(
        package='qrcode',
        executable='qrcode',
        output='screen',
        arguments=['--ros-args', '--log-level', 'info']
    )

    # ── 摄像头管线 ─────────────────────────────────────────────────
    # 非竞速模式才启动编码器 (编码器与解码器争抢 VPU，导致崩溃)
    _camera_actions = [usb_node, nv12_decode_node]
    if not _IS_RACE:
        _camera_actions.append(img_encode_node)
    start_camera_pipeline = TimerAction(
        period=LaunchConfiguration('camera_pipeline_delay'),
        actions=_camera_actions,
    )

    # ── 视觉管线 ─────────────────────────────────────────────────
    # 非竞速模式才启动 WebSocket (且需要 rosbridge)
    _vision_actions = [
        qrcode,
        racing_track_detection_resnet_go,
        racing_track_detection_resnet_s,
        racing_track_detection_resnet_n,
        racing_track_detection_resnet_back,
        racing_obstacle_detection_yolo,
        # vision_language_model,
        # racing_control,
    ]
    if not _IS_RACE:
        _vision_actions.append(web_node)
    start_vision_pipeline = TimerAction(
        period=LaunchConfiguration('vision_start_delay'),
        actions=_vision_actions,
    )

    start_after_camera_config = RegisterEventHandler(
        OnProcessExit(
            target_action=lock_camera,
            on_exit=[
                start_camera_pipeline,
                start_vision_pipeline,
            ],
        )
    )

    # ── 组装顶层 LaunchDescription ────────────────────────────────
    _top_actions = [lock_camera, start_after_camera_config]
    if not _IS_RACE:
        _top_actions.append(rosbridge_node)   # rosbridge 仅 WebSocket 需要
    _top_actions.append(origincar_base)

    return LaunchDescription(launch_args + _top_actions)
