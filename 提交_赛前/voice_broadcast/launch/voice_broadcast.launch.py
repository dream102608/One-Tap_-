"""
voice_broadcast.launch.py  —  语音播报 (edge-tts → ES8326)
用法:
    ros2 launch voice_broadcast voice_broadcast.launch.py

参数:
    volume_boost  ffmpeg 音量倍数 (默认 50.0)
    cooldown      播报冷却秒数 (默认 10.0)
"""
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument('volume_boost', default_value='50.0'),
        DeclareLaunchArgument('tts_rate',     default_value='+10%'),
        DeclareLaunchArgument('cooldown',     default_value='10.0'),
        DeclareLaunchArgument('enable_broadcast', default_value='True'),

        Node(
            package='voice_broadcast',
            executable='voice_broadcast',
            name='voice_broadcast',
            output='screen',
            parameters=[{
                'volume_boost':    LaunchConfiguration('volume_boost'),
                'tts_rate':        LaunchConfiguration('tts_rate'),
                'cooldown':        LaunchConfiguration('cooldown'),
                'enable_broadcast': LaunchConfiguration('enable_broadcast'),
            }]
        ),
    ])
