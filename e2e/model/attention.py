import torch
import torch.nn as nn
import torch.nn.functional as F


class LocationAwareAttention(nn.Module):
    r"""
    Multi-headed Location-Aware (Hybrid) Attention
    Applies a multi-head + location-aware attention mechanism on the output features from the decoder.
    Multi-head attention proposed in "Attention Is All You Need" paper.
    Location-aware attention proposed in "Attention-Based Models for Speech Recognition" paper.
    We combined these two attention mechanisms as custom.

    Args:
        hidden_dim (int): The number of expected features in the output
        num_heads (int): The number of heads. (default: )
        conv_out_channel (int): The number of out channel in convolution

    Inputs: query, value, prev_align
        - **query** (batch, q_len, hidden_dim): tensor containing the output features from the decoder.
        - **value** (batch, v_len, hidden_dim): tensor containing features of the encoded input sequence.
        - **prev_align** (batch_size * num_heads, v_len): tensor containing previous timestep`s alignment

    Returns: output, align
        - **output** (batch, output_len, dimensions): tensor containing the feature from encoder outputs
        - **align** (batch * num_heads, v_len): tensor containing the alignment from the encoder outputs.

    Reference:
        - **Attention Is All You Need**: https://arxiv.org/abs/1706.03762
        - **Attention-Based Models for Speech Recognition**: https://arxiv.org/abs/1506.07503
        - **State-Of-The-Art Speech Recognition with Sequence-to-Sequence Models**: https://arxiv.org/abs/1712.01769
    """
    def __init__(self, hidden_dim, num_heads=8, conv_out_channel=10):
        super().__init__()
        self.num_heads = num_heads
        self.dim = int(hidden_dim / num_heads)
        self.q_proj = nn.Linear(hidden_dim, self.dim * num_heads, bias=False)
        self.v_proj = nn.Linear(hidden_dim, self.dim * num_heads, bias=False)
        self.loc_proj = nn.Linear(conv_out_channel, self.dim, bias=False)
        self.conv1d = nn.Conv1d(num_heads, conv_out_channel, kernel_size=3, padding=1)
        self.bias = nn.Parameter(torch.rand(self.dim).uniform_(-0.1, 0.1))
        self.score_proj = nn.Linear(self.dim, 1, bias=True)
        self.output_proj = nn.Linear(hidden_dim << 1, hidden_dim, bias=True)

    def forward(self, query, value, prev_align):
        batch_size, seq_len = value.size(0), value.size(1)
        residual = query

        # Initialize previous alignment to zeros
        if prev_align is None:
            prev_align = value.new_zeros(batch_size, self.num_heads, seq_len)

        # Calculate location energy
        loc_energy = torch.tanh(self.loc_proj(self.conv1d(prev_align).transpose(1, 2)))
        loc_energy = loc_energy.unsqueeze(1).repeat(1, self.num_heads, 1, 1).view(-1, seq_len, self.dim)

        # Shape matching
        query = self.q_proj(query).view(batch_size, -1, self.num_heads, self.dim).permute(0, 2, 1, 3)
        value = self.v_proj(value).view(batch_size, -1, self.num_heads, self.dim).permute(0, 2, 1, 3)
        query = query.contiguous().view(-1, 1, self.dim)
        value = value.contiguous().view(-1, seq_len, self.dim)

        # Get attention score, alignment
        score = self.score_proj(torch.tanh(value + query + loc_energy + self.bias)).squeeze(2)
        align = F.softmax(score, dim=1)

        value = value.view(batch_size, seq_len, self.num_heads, self.dim).permute(0, 2, 1, 3)
        value = value.contiguous().view(-1, seq_len, self.dim)

        # Get context vector
        context = torch.bmm(align.unsqueeze(1), value).view(batch_size, -1, self.num_heads * self.dim)
        align = align.view(batch_size, self.num_heads, -1)

        # Get output
        combined = torch.cat([context, residual], dim=2)
        output = self.output_proj(combined.view(-1, self.hidden_dim << 1)).view(batch_size, -1, self.hidden_dim)

        return output, align
