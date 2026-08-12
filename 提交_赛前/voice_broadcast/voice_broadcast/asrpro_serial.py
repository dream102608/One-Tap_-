#!/usr/bin/env python3
"""
asrpro_serial.py  —  YB-MUE02-V2.0 串口驱动
=============================================
亚博智能离线语音模块 UART 通信协议：

物理层:
    波特率: 115200 (动态TTS), 9600 (兼容旧固件)
    数据位: 8
    停止位: 1
    校验位: None
    USB-UART: CH340 → /dev/ttyUSB0

TTS 帧格式 (主机 → 模块):
    ┌──────┬──────┬────────────────────┬──────┬──────┐
    │ 0xAA │ 0x55 │   GB2312 text bytes│ 0x55 │ 0xAA │
    └──────┴──────┴────────────────────┴──────┴──────┘

    文本编码: GB2312 (中文), ASCII 直通 (英文/数字)
"""

import serial
import threading


class ASRPRO:
    """YB-MUE02-V2.0 语音模块串口驱动"""

    FRAME_START1 = 0xAA
    FRAME_START2 = 0x55
    FRAME_END1   = 0x55
    FRAME_END2   = 0xAA

    def __init__(self, port='/dev/ttyUSB0', baud=115200, timeout=0.2):
        self.port = port
        self.baud = baud
        self.timeout = timeout
        self.ser = None
        self._lock = threading.Lock()
        self._connected = False

    # ================================================================
    def connect(self):
        try:
            self.ser = serial.Serial(
                port=self.port,
                baudrate=self.baud,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=self.timeout
            )
            self._connected = True
            return True
        except Exception:
            self._connected = False
            return False

    def disconnect(self):
        if self.ser and self.ser.is_open:
            self.ser.close()
        self._connected = False

    @property
    def is_connected(self):
        return self._connected and self.ser is not None and self.ser.is_open

    # ================================================================
    # TTS 动态播报 — 核心方法
    # ================================================================
    def send_tts(self, text):
        """
        发送中文文本到 YB-MUE02 进行动态 TTS 合成播报。
        编码: GB2312, 帧: AA 55 [GB2312 bytes] 55 AA
        """
        try:
            payload = text.encode('gb2312')
        except UnicodeEncodeError:
            # 如果 GB2312 编不了（极少数生僻字），用 GBK
            payload = text.encode('gbk', errors='replace')

        return self._send_frame(payload)

    # ================================================================
    # 基础帧发送 (内部使用)
    # ================================================================
    def _send_frame(self, data_bytes):
        frame = bytes([self.FRAME_START1, self.FRAME_START2]) \
              + bytes(data_bytes) \
              + bytes([self.FRAME_END1, self.FRAME_END2])
        with self._lock:
            if self.is_connected:
                self.ser.write(frame)
                self.ser.flush()
                return True
        return False

    def send_cmd1(self, d1, d2, d3):
        """3 字节指令 (兼容旧版 ID 播报)"""
        return self._send_frame([d1 & 0xFF, d2 & 0xFF, d3 & 0xFF])

    def send_cmd2(self, d1, d2):
        """2 字节指令 (兼容旧版)"""
        return self._send_frame([d1 & 0xFF, d2 & 0xFF])

    # ================================================================
    # 接收
    # ================================================================
    def read_result(self):
        with self._lock:
            if self.is_connected and self.ser.in_waiting >= 1:
                return self.ser.read(1)[0]
        return None

    def read_all(self):
        with self._lock:
            if self.is_connected and self.ser.in_waiting > 0:
                return self.ser.read(self.ser.in_waiting)
        return b''
