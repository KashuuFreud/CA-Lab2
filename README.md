# CA-Lab2

## 项目简介

CA-Lab2 是一个用于计算机体系结构上机实验二的 MIPS 五级流水线可视化模拟器。项目基于 Python Flask 与原生 HTML/CSS/JavaScript 实现，支持通过网页界面导入汇编测试程序，并观察指令在 IF、ID、EX、MEM、WB 五个阶段中的执行过程。

本项目重点用于演示和分析流水线中的 RAW 数据冲突、分支控制冲突、Stall、Flush 以及 Forwarding 对性能的影响。

## 功能特点

* 支持 MIPS 五级流水线可视化展示
* 支持单周期 Step 执行
* 支持连续 Run 执行
* 支持 Reset 重置模拟状态
* 支持 Forwarding 开关控制
* 支持从本地导入 `.asm` / `.s` / `.txt` 测试程序
* 支持寄存器、内存、PC、Cycle 等状态查看
* 支持统计 Cycles、Instructions、Stalls、Flushes、CPI
* 支持 Forwarding OFF / ON 自动性能对比
* 支持生成实验报告用分析文字与截图清单

## 项目结构

```text
CA-Lab2/
|-- app.py
|-- simulator.py
|-- programs/
|   |-- no_hazard.asm
|   |-- raw_hazard.asm
|   `-- branch.asm
|-- templates/
|   `-- index.html
|-- static/
|   |-- style.css
|   `-- main.js
`-- README.md
```

其中，`programs/` 目录中的 `.asm` 文件仅作为测试样例代码使用，不属于模拟器的内置程序逻辑。模拟器运行时支持用户在网页端自行导入新的汇编文件。

## 环境要求

建议使用 Python 3.8 及以上版本。

主要依赖：

```text
Flask
```

## 安装与运行

1. 克隆仓库：

```bash
git clone https://github.com/KashuuFreud/CA-Lab2.git
cd CA-Lab2
```

2. 创建虚拟环境：

Windows PowerShell：

```powershell
python -m venv .venv
.venv\Scripts\activate
```

macOS / Linux：

```bash
python3 -m venv .venv
source .venv/bin/activate
```

3. 安装依赖：

```bash
pip install -r requirements.txt
```

如果没有 `requirements.txt`，也可以直接安装：

```bash
pip install flask
```

4. 启动项目：

```bash
python app.py
```

5. 在浏览器中打开：

```text
http://127.0.0.1:5000
```

## 使用说明

进入网页后，可以在 Simulator 页面中导入本地 `.asm` 文件。导入后，程序源码会显示在 Source 区域。点击 Load 后，模拟器会载入当前程序。

常用操作如下：

* Load：载入当前导入的汇编程序
* Step：执行一个时钟周期
* Run：连续执行直到暂停或程序结束
* Reset：重置当前程序状态
* Forwarding：切换是否启用定向转发

Analysis 页面可以对同一程序分别在 Forwarding OFF 和 Forwarding ON 下运行，并自动生成 Cycles、Stalls 和 CPI 对比结果。

Report 页面可以生成实验报告中可使用的分析文字和截图建议。

## 支持的指令格式

当前模拟器主要支持以下简化 MIPS 指令：

```asm
add  r1, r2, r3
addi r1, r2, 4
lw   r1, 0, r2
sw   r1, 0, r2
beqz r1, label
halt
```

说明：

* 寄存器格式使用 `r0` 到 `r31`
* `r0` 固定为 0
* 分支目标通过标签表示
* `halt` 用于表示程序结束

## 关于 programs 目录

`programs/` 目录仅用于存放实验测试代码，方便快速验证无冲突、RAW 冲突和分支冲突等场景。它不是模拟器逻辑的一部分，也不是“内置程序库”。

本项目已经支持通过网页导入外部汇编文件，因此测试者可以自行编写新的 `.asm` 文件进行验证。


