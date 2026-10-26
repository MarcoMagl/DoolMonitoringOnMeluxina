### Author: Vasilis Vryniotis <bbriniotis@datumbox.com>

class dool_plugin(dool):
    """
    Total GPU usage for NVIDIA cards. Requires the nvidia-ml-py package.

    Usage: dstat --nvidia-gpu
    """

    def __init__(self):
        self.name = 'gpu usage nvidia'
        self.type = 'p'
        self.width = 5
        self.scale = 34
        self.cols = 1
        self.samples = 10

    def check(self):
        try:
            import pynvml
            pynvml.nvmlInit()
        except:
            raise Exception('The "pynvml" library is missing from this system.')

    def vars(self):
        ret = ['total']
        if op.full:
            import pynvml
            deviceCount = pynvml.nvmlDeviceGetCount()
            for i in range(0, deviceCount):
                ret.append('gpu%d' % i)
        return ret

    def extract(self):
        stats = self._getUsagePerGPU(self.samples)
        stats['total'] = self._getTotalUsage(stats)
        for name in self.vars:
            self.val[name] = stats[name]

    def _getUsagePerGPU(self, samples):
        import pynvml
        usage = {}
        deviceCount = pynvml.nvmlDeviceGetCount()
        for iter in range(0, samples):
            for i in range(0, deviceCount):
                name = 'gpu%d' % i
                handle = pynvml.nvmlDeviceGetHandleByIndex(i)
                if name not in usage:
                    usage[name] = 0.0
                usage[name] += pynvml.nvmlDeviceGetUtilizationRates(handle).gpu / float(samples)
        return usage

    def _getTotalUsage(self, usage_per_gpu):
        return sum(usage_per_gpu.values()) / len(usage_per_gpu)

