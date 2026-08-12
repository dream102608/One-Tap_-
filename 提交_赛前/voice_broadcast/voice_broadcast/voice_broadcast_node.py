#!/usr/bin/env python3
"""voice_broadcast_node.py — edge-tts → 板载/USB声卡"""

import os, re, time, asyncio, subprocess
import rclpy
from rclpy.node import Node
from std_msgs.msg import String, Int32

class VoiceBroadcastNode(Node):
    def __init__(self):
        super().__init__('voice_broadcast')
        self.declare_parameter('enable_broadcast', True)
        self.declare_parameter('cooldown', 15.0)
        self.declare_parameter('qr_cooldown', 15.0)
        self.declare_parameter('volume_boost', 3.0)
        self._last_text = ''
        self._broadcast_count = 0
        self._last_broadcast_time = 0.0
        self._qr_last_broadcast = 0.0
        self._qr_raw = ''
        self._qr_raw_time = 0.0
        self._qr_number = 0
        self._qr_number_time = 0.0
        self._dev = self._detect_device()
        self.create_subscription(String, '/image_analysis_result', self.result_callback, 10)
        self.create_subscription(Int32, '/qrcode_number', self.qrcode_callback, 10)
        self.create_subscription(String, '/qrcode_raw', self.qrcode_raw_callback, 10)
        self.get_logger().info(f"语音播报节点已启动 (设备: {self._dev})")

    def _detect_device(self):
        try:
            out = subprocess.check_output(['aplay', '-l'], text=True, stderr=subprocess.STDOUT)
            es = None
            for line in out.splitlines():
                m = re.search(r'card\s+(\d+).*device\s+(\d+)', line)
                if m:
                    dev = f'plughw:{m.group(1)},{m.group(2)}'
                    if 'usb' in line.lower(): return dev
                    if 'es8326' in line.lower(): es = dev
            if es: return es
        except: pass
        return 'plughw:2,0'

    def _try_qr_broadcast(self):
        """数字+方向双齐且冷却期外 → 播报并更新时间戳"""
        now = time.time()
        if now - self._qr_last_broadcast < self.get_parameter('qr_cooldown').value:
            return
        if not (self._qr_raw and self._qr_number):
            return
        if now - self._qr_raw_time > 3.0 or now - self._qr_number_time > 3.0:
            return
        d = '顺时针' if self._qr_number == 3 else '逆时针'
        t = f"{self._qr_raw} {d}方向"
        self.get_logger().info(f"[二维码播报] {t}")
        self._speak(t)
        self._qr_last_broadcast = now

    def qrcode_raw_callback(self, msg: String):
        raw = msg.data.strip()
        if not raw: return
        self._qr_raw = raw
        self._qr_raw_time = time.time()
        self._try_qr_broadcast()

    def qrcode_callback(self, msg: Int32):
        if msg.data not in (3, 4): return
        self._last_text = ''
        self._last_broadcast_time = 0.0
        self._qr_number = msg.data
        self._qr_number_time = time.time()
        self._try_qr_broadcast()

    def result_callback(self, msg: String):
        raw = msg.data.strip()
        if not raw or not self.get_parameter('enable_broadcast').value: return
        text = self._extract_result(raw)
        if not text: return
        if not self._is_valid(text):
            self.get_logger().info(f"跳过无效: {text}")
            return
        now = time.time()
        if now - self._last_broadcast_time < self.get_parameter('cooldown').value: return
        self._last_broadcast_time = now
        self._broadcast_count += 1
        self.get_logger().info(f"[播报 #{self._broadcast_count}] {text}")
        self._speak(text)

    def _speak(self, text):
        try: import edge_tts
        except ImportError:
            self.get_logger().error("edge-tts 未安装!"); return
        mp3 = '/tmp/tts_edge.mp3'; wav = '/tmp/tts_edge.wav'
        v = str(self.get_parameter('volume_boost').value)
        try:
            async def g():
                c = edge_tts.Communicate(text=text, voice='zh-CN-XiaoxiaoNeural', rate='+50%', pitch='+0Hz')
                await c.save(mp3)
            asyncio.new_event_loop().run_until_complete(g())
            subprocess.run(['ffmpeg', '-y', '-i', mp3, '-ar', '48000', '-ac', '2', '-af', f'volume={v}', wav], timeout=15, capture_output=True, check=True)
            subprocess.run(['aplay', '-D', self._dev, '-q', wav], timeout=15, check=False)
        except Exception as e:
            self.get_logger().error(f"播报异常: {e}")

    def _extract_result(self, raw):
        text = re.sub(r'^图像分析结果[：:]?\s*', '', raw).strip()
        return text if text and len(text)>=4 and not re.match(r'^[\d\s\W_]+$', text) else ''

    def _is_valid(self, text):
        if any(k in text for k in ('无','没有','未','不','很抱歉','无法','不能','不存在','未发现','图中无','当前图片','请求')): return False
        f = {'姿态':('躺卧','躺','卧'),'性别':('男性','女性','男','女'),'衣着':('背心','白背心','衣服','病号服'),'医疗':('绷带','输液','枕头','病人','手臂','蓝色')}
        return sum(1 for v in f.values() if any(k in text for k in v)) >= 2

def main(args=None):
    rclpy.init(args=args)
    node = None
    try:
        node = VoiceBroadcastNode()
        rclpy.spin(node)
    except KeyboardInterrupt: pass
    finally:
        if node: node.destroy_node()
        rclpy.shutdown() if rclpy.ok() else None

if __name__ == '__main__':
    main()
