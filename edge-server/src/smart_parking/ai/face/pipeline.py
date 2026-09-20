"""Face Processing Pipeline."""
class FacePipeline:
    def __init__(self, adapter):
        self.adapter = adapter

    def process(self, frame):
        """Thực thi chuỗi phát hiện, kiểm tra chất lượng, liveness và trích xuất embedding."""
        return None