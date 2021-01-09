# Copyright (c) 2020, Soohwan Kim. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import torch.nn as nn
import torch.nn.functional as F

from torch import Tensor
from typing import Tuple
from kospeech.models.jasper import JasperDecoderConfig
from kospeech.models.jasper.sublayers import JasperSubBlock


class JasperDecoder(nn.Module):
    """
    Jasper Encoder consists of three post-processing blocks.

    Args:
        config (JasperDecoderConfig): configurations of Jasper Decoder

    Inputs: inputs, input_lengths, residual
        - **inputs**: tensor contains input sequence vector
        - **input_lengths**: tensor contains sequence lengths

    Returns: output, output_lengths
        - **output**: tensor contains output sequence vector
        - **output**: tensor contains output sequence lengths
    """

    def __init__(self, config: JasperDecoderConfig):
        super(JasperDecoder, self).__init__()
        self.layers = nn.ModuleList([
            JasperSubBlock(
                in_channels=config.block['in_channels'][i],
                out_channels=config.block['out_channels'][i],
                kernel_size=config.block['kernel_size'][i],
                dilation=config.block['dilation'][i],
                dropout_p=config.block['dropout_p'][i],
                activation='relu',
                bias=True if i == 2 else False
            ) for i in range(3)
        ])

    def forward(self, encoder_outputs: Tensor, encoder_output_lengths: Tensor) -> Tuple[Tensor, Tensor]:
        output, output_lengths = encoder_outputs, encoder_output_lengths

        for layer in self.layers:
            output, output_lengths = layer(encoder_outputs, encoder_output_lengths)

        output = F.log_softmax(output, dim=-1)

        return output, output_lengths
