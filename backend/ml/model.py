"""LSTM 温度预测模型定义。与训练端 ml_training/model.py 保持一致。"""

import torch.nn as nn


class TemperatureLSTM(nn.Module):
    def __init__(self, input_size=1, hidden_size=32, num_layers=1):
        super().__init__()
        self.lstm = nn.LSTM(input_size, hidden_size, num_layers, batch_first=True)
        self.fc = nn.Linear(hidden_size, 1)

    def forward(self, x):
        # x: (batch, seq_len, 1)
        out, _ = self.lstm(x)
        return self.fc(out[:, -1, :])  # (batch, 1)
