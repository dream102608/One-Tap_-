from launch import LaunchDescription
from launch_ros.actions import Node

def generate_launch_description():

    nav2_params = '/YOUR_ROS_WS/src/my_nav/config/nav2_params.yaml'

    return LaunchDescription([

        # ȫ�ֹ滮��
        Node(
            package='nav2_planner',
            executable='planner_server',
            name='planner_server',
            output='screen',
            parameters=[nav2_params]
        ),

        # �ֲ�������
        Node(
            package='nav2_controller',
            executable='controller_server',
            name='controller_server',
            output='screen',
            parameters=[nav2_params]
        ),

        # ��Ϊ����������� spin / backup / wait��
        Node(
            package='nav2_behaviors',
            executable='behavior_server',
            name='behavior_server',
            output='screen',
            parameters=[nav2_params]
        ),

        # ��Ϊ��������
        Node(
            package='nav2_bt_navigator',
            executable='bt_navigator',
            name='bt_navigator',
            output='screen',
            parameters=[nav2_params]
        ),

        # �������ڹ�������ֻ���������ڵ㣬���� map_server/amcl��
        Node(
            package='nav2_lifecycle_manager',
            executable='lifecycle_manager',
            name='lifecycle_manager_navigation',
            output='screen',
            parameters=[{
                'use_sim_time': False,
                'autostart': True,
                'node_names': [
                    'planner_server',
                    'controller_server',
                    'behavior_server',
                    'bt_navigator'
                ]
            }]
        )

    ])