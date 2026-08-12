/*
 * FlowCC ESP32 参考固件 v1.3
 * ---------------------------
 * 与 FlowCC 桌面软件的「串口协议 v1.1」完全对应：
 *   主机 -> 设备: PWR 0/1 | SPD 1..3 | OSC 0/1 | ANG 0..180 | STATE? | PING
 *   设备 -> 主机: OK <CMD> | ERR <CMD> <CODE> | STATE pwr=x spd=x osc=x ang=x | PONG | HELLO FLOWCC 1.3
 *
 * 传输方式三选一（编译前修改 FLOWCC_TRANSPORT）：
 *   SERIAL  USB 串口，115200 8N1
 *   WIFI    TCP 服务，端口 3333（填写 WIFI_SSID / WIFI_PASS）
 *   BLE     BLE NUS（Nordic UART Service），广播名 FlowCC
 *
 * 硬件接线（以 ESP32 DevKit V1 为例）:
 *   GPIO25 --[1kΩ 电阻]--> N 沟道 MOSFET 栅极（如 AO3400 / IRLZ44N）
 *            MOSFET 源极 -> GND；漏极 -> 风扇负极；风扇正极 -> 电源正极
 *            风扇两端并联续流二极管 1N4007（方向：正极朝风扇电源正）
 *            栅极与 GND 之间接 10kΩ 下拉电阻，防止上电瞬间误启动
 *   GPIO26 --> 舵机信号线（SG90，用于摇头机构），红线 5V，棕线 GND
 *   风扇电源：5V 小风扇可用 USB 供电；12V 风扇需独立电源，与 ESP32 共地
 *
 * 说明:
 *   - 风扇 PWM 频率 20kHz（超出人耳范围，无电流声），8 位分辨率
 *   - 舵机用 LEDC 50Hz PWM 模拟，无需额外库
 *   - 档位 -> PWM 占空比映射见 SPEED_DUTY，可按实际风扇调整
 */

#define SERIAL 0
#define WIFI 1
#define BLE 2

#define FLOWCC_TRANSPORT SERIAL
#define WIFI_SSID "your-ssid"
#define WIFI_PASS "your-pass"
#define TCP_PORT 3333

const char FW_VERSION[] = "1.3";

// ---- 引脚与参数 ----
const int FAN_PWM_PIN   = 25;
const int SERVO_PIN     = 26;
const int PWM_FREQ      = 20000;   // 风扇 PWM 频率 Hz
const int PWM_RES       = 8;       // 8 位分辨率 0~255
const int SERVO_FREQ    = 50;      // 舵机 PWM 频率 Hz
const int SERVO_RES     = 16;      // 16 位分辨率
const int SERVO_MAX     = 65535;   // 16 位满量程对应 20ms 周期
const unsigned long SERVO_STEP_MS = 15;  // 摇头步进间隔

// 档位 -> PWM 占空比（0~255）。若风扇起步电压高，可抬高 1 档数值。
const int SPEED_DUTY[4] = {0, 100, 175, 255};

// ---- 状态 ----
bool  g_power = false;
int   g_speed = 1;      // 1..3
bool  g_osc   = false;
int   g_angle = 90;     // 手动摆头目标角度 0..180
int   g_servo_pos   = 90;   // 0..180
int   g_servo_dir   = 1;
unsigned long g_last_servo_ms = 0;
String g_line_buf;

void handleCommand(String line);  // 前置声明

// ---- 传输层（按 FLOWCC_TRANSPORT 编译） ----
#if FLOWCC_TRANSPORT == WIFI
#include <WiFi.h>
WiFiServer g_server(TCP_PORT);
WiFiClient g_client;
#elif FLOWCC_TRANSPORT == BLE
#include <BLEDevice.h>
#include <BLEServer.h>
#define NUS_SERVICE "6e400001-b5a3-f393-e0a9-e50e24dcca9e"
#define NUS_RX      "6e400002-b5a3-f393-e0a9-e50e24dcca9e"
#define NUS_TX      "6e400003-b5a3-f393-e0a9-e50e24dcca9e"
BLECharacteristic *g_tx = nullptr;
bool g_ble_connected = false;
#endif

void sendLine(const String &line) {
#if FLOWCC_TRANSPORT == SERIAL
  Serial.println(line);
#elif FLOWCC_TRANSPORT == WIFI
  if (g_client) g_client.println(line);
#elif FLOWCC_TRANSPORT == BLE
  if (g_ble_connected && g_tx) {
    String out = line + "\n";
    g_tx->setValue((uint8_t *)out.c_str(), out.length());
    g_tx->notify();
  }
#endif
}

void feedChar(char c) {
  if (c == '\n') {
    String line = g_line_buf;
    g_line_buf = "";
    handleCommand(line);
  } else if (c != '\r') {
    if (g_line_buf.length() < 64) g_line_buf += c;
  }
}

// ---- 输出控制 ----
void applyFan() {
  int duty = (g_power) ? SPEED_DUTY[g_speed] : 0;
  ledcWrite(FAN_PWM_PIN, duty);
}

void writeServo(int pos) {
  // 0..180 度映射到 1000..2000us 脉宽；20ms 周期下换算 16 位占空比
  long width_us = 1000L + (long)pos * 1000L / 180L;
  int duty = (int)(width_us * SERVO_MAX / 20000L);
  ledcWrite(SERVO_PIN, duty);
}

void reportState() {
  String s = "STATE pwr=";
  s += g_power ? 1 : 0;
  s += " spd="; s += g_speed;
  s += " osc="; s += g_osc ? 1 : 0;
  s += " ang="; s += g_angle;
  sendLine(s);
}

void handleCommand(String line) {
  line.trim();
  if (line.length() == 0) return;

  int sp = line.indexOf(' ');
  String cmd = (sp < 0) ? line : line.substring(0, sp);
  String arg = (sp < 0) ? "" : line.substring(sp + 1);
  cmd.trim();
  arg.trim();

  if (cmd == "PING") { sendLine("PONG"); return; }
  if (cmd == "STATE?") { sendLine("OK STATE?"); reportState(); return; }
  if (cmd == "PWR") {
    if (arg != "0" && arg != "1") { sendLine("ERR PWR BADARG"); return; }
    g_power = (arg == "1");
    applyFan();
    sendLine("OK PWR"); reportState(); return;
  }
  if (cmd == "SPD") {
    int level = arg.toInt();
    if (level < 1 || level > 3 || String(level) != arg) { sendLine("ERR SPD BADARG"); return; }
    g_speed = level;
    applyFan();
    sendLine("OK SPD"); reportState(); return;
  }
  if (cmd == "OSC") {
    if (arg != "0" && arg != "1") { sendLine("ERR OSC BADARG"); return; }
    g_osc = (arg == "1");
    sendLine("OK OSC"); reportState(); return;
  }
  if (cmd == "ANG") {
    int deg = arg.toInt();
    if (deg < 0 || deg > 180 || String(deg) != arg) { sendLine("ERR ANG BADARG"); return; }
    g_osc = false;      // 手动摆头即退出自动摇头
    g_angle = deg;
    sendLine("OK ANG"); reportState(); return;
  }
  sendLine("ERR " + cmd + " UNSUPPORTED");
}

// ---- 摇头 ----
void tickServo() {
  unsigned long now = millis();
  if (now - g_last_servo_ms < SERVO_STEP_MS) return;
  g_last_servo_ms = now;
  if (!g_osc) {
    if (g_servo_pos == g_angle) return;   // 已到位
    if (g_servo_pos < g_angle) g_servo_pos++;
    else g_servo_pos--;
    writeServo(g_servo_pos);
    return;
  }
  g_servo_pos += g_servo_dir;
  if (g_servo_pos >= 180) { g_servo_pos = 180; g_servo_dir = -1; }
  if (g_servo_pos <= 0)   { g_servo_pos = 0;   g_servo_dir = 1;  }
  writeServo(g_servo_pos);
}

// ---- BLE 回调 ----
#if FLOWCC_TRANSPORT == BLE
class RxCallback : public BLECharacteristicCallbacks {
  void onWrite(BLECharacteristic *c) override {
    std::string v = c->getValue();
    for (char ch : v) feedChar(ch);
  }
};
class ServerCallbacks : public BLEServerCallbacks {
  void onConnect(BLEServer *) override { g_ble_connected = true; }
  void onDisconnect(BLEServer *) override { g_ble_connected = false; }
};
#endif

// ---- Arduino 入口 ----
void setup() {
  ledcAttach(FAN_PWM_PIN, PWM_FREQ, PWM_RES);    // ESP32 Arduino Core 3.x API
  ledcAttach(SERVO_PIN, SERVO_FREQ, SERVO_RES);  // 旧版核心请改用 ledcSetup + ledcAttachPin
  applyFan();
  writeServo(g_servo_pos);

#if FLOWCC_TRANSPORT == SERIAL
  Serial.begin(115200);
  delay(50);
  sendLine(String("HELLO FLOWCC ") + FW_VERSION);
#elif FLOWCC_TRANSPORT == WIFI
  Serial.begin(115200);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  while (WiFi.status() != WL_CONNECTED) { delay(200); }
  g_server.begin();
  Serial.print("FlowCC WiFi IP: ");
  Serial.println(WiFi.localIP());   // 串口监视器查看 IP，填入软件连接栏
#elif FLOWCC_TRANSPORT == BLE
  BLEDevice::init("FlowCC");
  BLEServer *server = BLEDevice::createServer();
  server->setCallbacks(new ServerCallbacks());
  BLEService *svc = server->createService(NUS_SERVICE);
  g_tx = svc->createCharacteristic(NUS_TX, BLECharacteristic::PROPERTY_NOTIFY);
  BLECharacteristic *rx = svc->createCharacteristic(
      NUS_RX, BLECharacteristic::PROPERTY_WRITE | BLECharacteristic::PROPERTY_WRITE_NR);
  rx->setCallbacks(new RxCallback());
  svc->start();
  BLEAdvertising *adv = server->getAdvertising();
  adv->addServiceUUID(NUS_SERVICE);
  adv->start();
#endif
}

void loop() {
#if FLOWCC_TRANSPORT == SERIAL
  while (Serial.available() > 0) feedChar((char)Serial.read());
#elif FLOWCC_TRANSPORT == WIFI
  if (!g_client || !g_client.connected()) {
    g_client = g_server.available();   // 等待/接受新客户端
    if (g_client) sendLine(String("HELLO FLOWCC ") + FW_VERSION);
  } else {
    while (g_client.available() > 0) feedChar((char)g_client.read());
  }
#endif
  tickServo();
}
