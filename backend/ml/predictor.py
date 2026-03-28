"""LSTM 温度预测推理单例。"""

from __future__ import annotations

import logging
import os
from typing import Optional

import torch

from ml.model import TemperatureLSTM

logger = logging.getLogger(__name__)


class TemperaturePredictor:
    _instance: Optional["TemperaturePredictor"] = None

    def __init__(self, model_path: str):
        if not os.path.isfile(model_path):
            raise FileNotFoundError(f"模型文件不存在: {model_path}")

        # 自定义 checkpoint 含 float 与 state_dict，非纯权重；weights_only=True 会拒绝加载
        checkpoint = torch.load(model_path, map_location="cpu", weights_only=False)
        self.mean: float = checkpoint["mean"]
        self.std: float = checkpoint["std"]
        self.window_size: int = checkpoint["window_size"]

        self.model = TemperatureLSTM(
            input_size=1,
            hidden_size=checkpoint["hidden_size"],
            num_layers=checkpoint["num_layers"],
        )
        self.model.load_state_dict(checkpoint["model_state_dict"])
        self.model.eval()
        logger.info(
            "LSTM 温度预测模型已加载 (window=%d, mean=%.2f, std=%.2f)",
            self.window_size, self.mean, self.std,
        )

    def predict(self, recent_temps: list[float]) -> float:
        """输入最近 window_size 个小时温度（℃），返回下 1 小时预测温度（℃）。"""
        vals = recent_temps[-self.window_size:]
        if len(vals) < self.window_size:
            raise ValueError(
                f"需要至少 {self.window_size} 个温度值，实际 {len(vals)}"
            )
        normed = [(v - self.mean) / (self.std + 1e-8) for v in vals]
        x = torch.FloatTensor(normed).unsqueeze(0).unsqueeze(-1)  # (1, window, 1)
        with torch.no_grad():
            pred = self.model(x).item()
        return round(pred * (self.std + 1e-8) + self.mean, 2)

    def predict_rollout(self, recent_temps: list[float], steps: int) -> list[float]:
        """
        自回归多步：每步用上一窗口预测下一步，与训练时「下一步」目标一致；
        步数越多误差会累积，仅用于展示趋势。
        """
        if steps < 1:
            return []
        w = self.window_size
        window = list(recent_temps[-w:])
        if len(window) < w:
            raise ValueError(f"需要至少 {w} 个温度值，实际 {len(window)}")
        out: list[float] = []
        for _ in range(steps):
            p = self.predict(window)
            out.append(p)
            window = window[1:] + [p]
        return out

    @classmethod
    def get_instance(cls, model_path: str) -> "TemperaturePredictor":
        if cls._instance is None:
            cls._instance = cls(model_path)
        return cls._instance
