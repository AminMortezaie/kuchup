package opsagent

import (
	"bufio"
	"fmt"
	"os"
	"strconv"
	"strings"
	"syscall"
)

func hostSamples(procRoot, hostRoot, instance string) ([]Sample, error) {
	mem, err := memAvailableBytes(procRoot)
	if err != nil {
		return nil, err
	}
	load1, err := load1(procRoot)
	if err != nil {
		return nil, err
	}
	avail, size, err := rootFilesystemBytes(hostRoot)
	if err != nil {
		return nil, err
	}
	base := map[string]string{
		"instance": instance,
		"job":      "integrations/node_exporter",
	}
	fsLabels := map[string]string{
		"instance":   instance,
		"job":        "integrations/node_exporter",
		"mountpoint": "/",
		"fstype":     "rootfs",
		"device":     "/dev/root",
	}
	out := []Sample{
		{Metric: "node_memory_MemAvailable_bytes", Labels: copyLabels(base), Value: float64(mem)},
		{Metric: "node_load1", Labels: copyLabels(base), Value: load1},
		{Metric: "node_filesystem_avail_bytes", Labels: copyLabels(fsLabels), Value: float64(avail)},
		{Metric: "node_filesystem_size_bytes", Labels: copyLabels(fsLabels), Value: float64(size)},
	}
	return out, nil
}

func copyLabels(in map[string]string) map[string]string {
	out := make(map[string]string, len(in))
	for k, v := range in {
		out[k] = v
	}
	return out
}

func memAvailableBytes(procRoot string) (uint64, error) {
	f, err := os.Open(procRoot + "/meminfo")
	if err != nil {
		return 0, err
	}
	defer f.Close()
	sc := bufio.NewScanner(f)
	for sc.Scan() {
		line := sc.Text()
		if !strings.HasPrefix(line, "MemAvailable:") {
			continue
		}
		fields := strings.Fields(line)
		if len(fields) < 2 {
			break
		}
		kb, err := strconv.ParseUint(fields[1], 10, 64)
		if err != nil {
			return 0, err
		}
		return kb * 1024, nil
	}
	return 0, fmt.Errorf("MemAvailable not found in %s/meminfo", procRoot)
}

func load1(procRoot string) (float64, error) {
	data, err := os.ReadFile(procRoot + "/loadavg")
	if err != nil {
		return 0, err
	}
	fields := strings.Fields(string(data))
	if len(fields) < 1 {
		return 0, fmt.Errorf("loadavg empty")
	}
	return strconv.ParseFloat(fields[0], 64)
}

func rootFilesystemBytes(hostRoot string) (avail uint64, size uint64, err error) {
	path := hostRoot
	if path == "" {
		path = "/"
	}
	var st syscall.Statfs_t
	if err := syscall.Statfs(path, &st); err != nil {
		return 0, 0, err
	}
	size = st.Blocks * uint64(st.Bsize)
	avail = st.Bavail * uint64(st.Bsize)
	return avail, size, nil
}
