"""FlowCC 串口通信协议 v1。

设计原则：ASCII 行协议，LF(\n) 结尾，人类可读，可直接用任意串口助手调试。

主机(软件) -> 设备(固件):
    PWR <0|1>      设置电源
    SPD <1..3>     设置风速档位
    OSC <0|1>      设置摇头
    STATE?         查询状态
    PING           心跳

设备(固件) -> 主机(软件):
    OK <CMD>                命令执行成功
    ERR <CMD> <CODE>        命令执行失败, CODE: BADARG / UNSUPPORTED / INTERNAL
    STATE pwr=<0|1> spd=<1..3> osc=<0|1>   状态上报（执行命令后自动上报）
    PONG                    心跳回复
    HELLO FLOWCC <版本>      设备上电/复位后的问候帧
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

PROTOCOL_VERSION = "1.0"

SPEED_MIN = 1
SPEED_MAX = 3
DEFAULT_BAUD = 115200

CMD_POWER = "PWR"
CMD_SPEED = "SPD"
CMD_OSC = "OSC"
CMD_QUERY = "STATE?"
CMD_PING = "PING"

ERR_BADARG = "BADARG"
ERR_UNSUPPORTED = "UNSUPPORTED"
ERR_INTERNAL = "INTERNAL"


class MessageKind(Enum):
    OK = "OK"
    ERR = "ERR"
    STATE = "STATE"
    PONG = "PONG"
    HELLO = "HELLO"
    UNKNOWN = "UNKNOWN"


@dataclass
class FanState:
    """设备侧风扇状态。"""

    power: bool = False
    speed: int = SPEED_MIN
    oscillation: bool = False

    def encode_payload(self) -> str:
        return "pwr=%d spd=%d osc=%d" % (
            1 if self.power else 0,
            self.speed,
            1 if self.oscillation else 0,
        )


@dataclass
class Message:
    kind: MessageKind
    command: Optional[str] = None      # OK / ERR 帧对应的命令
    error_code: Optional[str] = None   # ERR 帧错误码
    state: Optional[FanState] = None   # STATE 帧携带的状态
    version: Optional[str] = None      # HELLO 帧固件版本
    raw: str = ""


# ---------------------------------------------------------------------------
# 编码（主机 -> 设备）
# ---------------------------------------------------------------------------

def encode_command(command: str, arg: Optional[object] = None) -> str:
    if arg is None:
        return f"{command}\n"
    return f"{command} {arg}\n"


def encode_power(on: bool) -> str:
    return encode_command(CMD_POWER, 1 if on else 0)


def encode_speed(level: int) -> str:
    level = int(level)
    if not SPEED_MIN <= level <= SPEED_MAX:
        raise ValueError(f"档位必须在 {SPEED_MIN}~{SPEED_MAX} 之间: {level}")
    return encode_command(CMD_SPEED, level)


def encode_oscillation(on: bool) -> str:
    return encode_command(CMD_OSC, 1 if on else 0)


def encode_query() -> str:
    return encode_command(CMD_QUERY)


def encode_ping() -> str:
    return encode_command(CMD_PING)


# ---------------------------------------------------------------------------
# 解码（设备 -> 主机）
# ---------------------------------------------------------------------------

def parse_state_payload(payload: str) -> FanState:
    """解析 'pwr=1 spd=2 osc=0' 形式的状态负载。"""
    fields = {}
    for token in payload.split():
        if "=" in token:
            key, value = token.split("=", 1)
            fields[key.strip().lower()] = value.strip()
    if "pwr" not in fields or "spd" not in fields or "osc" not in fields:
        raise ValueError(f"状态负载缺少字段: {payload!r}")
    speed = int(fields["spd"])
    if not SPEED_MIN <= speed <= SPEED_MAX:
        raise ValueError(f"非法档位: {speed}")
    return FanState(
        power=fields["pwr"] == "1",
        speed=speed,
        oscillation=fields["osc"] == "1",
    )


def parse_line(line: str) -> Message:
    """解析一行设备输出。无法识别时返回 UNKNOWN，绝不抛异常。"""
    text = line.strip()
    if not text:
        return Message(kind=MessageKind.UNKNOWN, raw=text)

    parts = text.split()
    head = parts[0].upper()

    if head == "OK" and len(parts) >= 2:
        return Message(kind=MessageKind.OK, command=parts[1].upper(), raw=text)
    if head == "ERR" and len(parts) >= 3:
        return Message(kind=MessageKind.ERR, command=parts[1].upper(),
                       error_code=parts[2], raw=text)
    if head == "STATE":
        try:
            state = parse_state_payload(" ".join(parts[1:]))
        except ValueError:
            return Message(kind=MessageKind.UNKNOWN, raw=text)
        return Message(kind=MessageKind.STATE, state=state, raw=text)
    if head == "PONG":
        return Message(kind=MessageKind.PONG, raw=text)
    if head == "HELLO":
        version = parts[2] if len(parts) >= 3 else None
        return Message(kind=MessageKind.HELLO, version=version, raw=text)
    return Message(kind=MessageKind.UNKNOWN, raw=text)
