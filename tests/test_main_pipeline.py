import pandas as pd

from main import save_output_files, should_run_nowcoder


def test_should_run_nowcoder_only_when_final_count_is_short():
    assert should_run_nowcoder(449, 450) is True
    assert should_run_nowcoder(450, 450) is False


def test_save_output_files_writes_raw_and_final(tmp_path):
    raw_jobs = [{"岗位名称": "数据分析实习生", "公司名称": "甲公司"}]
    final_df = pd.DataFrame([{"岗位名称": "数据分析实习生", "公司名称": "甲公司"}])
    paths = save_output_files(raw_jobs, final_df, output_dir=tmp_path)
    assert paths["raw"].exists()
    assert paths["final"].exists()
