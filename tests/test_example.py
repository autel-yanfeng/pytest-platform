"""示例测试文件，验证平台基本功能"""
import pytest


def add(a: float, b: float) -> float:
    return a + b


def divide(a: float, b: float) -> float:
    if b == 0:
        raise ValueError("除数不能为零")
    return a / b


class TestAdd:
    @pytest.mark.parametrize("a, b, expected", [
        (1, 2, 3),
        (-1, 1, 0),
        (0, 0, 0),
    ])
    def test_add_normal(self, a: float, b: float, expected: float):
        # Arrange - 参数通过 parametrize 传入
        # Act
        result = add(a, b)
        # Assert
        assert result == expected


class TestDivide:
    def test_divide_normal(self):
        # Arrange
        a, b = 10.0, 4.0
        # Act
        result = divide(a, b)
        # Assert
        assert result == pytest.approx(2.5)

    def test_divide_by_zero_raises(self):
        with pytest.raises(ValueError, match="除数不能为零"):
            divide(1, 0)
