import csv
import os


def export_first_five_rows(source_file, target_file):
    """
    提取CSV文件的前5行并保存为新的CSV文件

    Args:
        source_file (str): 源CSV文件路径
        target_file (str): 目标CSV文件路径
    """
    # 检查源文件是否存在
    if not os.path.exists(source_file):
        print(f"错误：源文件 '{source_file}' 不存在！")
        return

    try:
        # 读取源文件并提取前5行
        with open(source_file, "r", newline="", encoding="utf-8") as infile:
            # 创建CSV读取器
            csv_reader = csv.reader(infile)
            # 提取前5行数据（包括表头）
            first_five_rows = []
            for i, row in enumerate(csv_reader):
                if i < 5:
                    first_five_rows.append(row)
                else:
                    break

        # 将提取的数据写入新文件
        with open(target_file, "w", newline="", encoding="utf-8") as outfile:
            csv_writer = csv.writer(outfile)
            csv_writer.writerows(first_five_rows)

        print(f"成功！已将 '{source_file}' 的前5行导出到 '{target_file}'")
        print(f"共导出 {len(first_five_rows)} 行数据")

    except Exception as e:
        print(f"处理文件时出错：{e}")


# ------------------- 配置部分（请修改这里的文件路径） -------------------
# 源CSV文件路径（替换成你的文件路径）
SOURCE_CSV = "export_data/sinafinance_daily_dedup.csv"
# 新CSV文件路径（输出文件路径）
TARGET_CSV = "news_demo.csv"

# 执行函数
if __name__ == "__main__":
    export_first_five_rows(SOURCE_CSV, TARGET_CSV)
