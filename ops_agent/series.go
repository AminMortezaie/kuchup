package opsagent

import (
	"encoding/binary"
	"math"
	"time"
)

type Sample struct {
	Metric string
	Labels map[string]string
	Value  float64
	At     time.Time
}

func copyLabels(in map[string]string) map[string]string {
	out := make(map[string]string, len(in))
	for k, v := range in {
		out[k] = v
	}
	return out
}

func samplesToWriteRequest(samples []Sample) []byte {
	var out []byte
	for i := range samples {
		out = appendTagBytes(out, 1, marshalTimeSeries(samples[i]))
	}
	return out
}

func marshalTimeSeries(s Sample) []byte {
	var msg []byte
	msg = appendTagBytes(msg, 1, marshalLabel("__name__", s.Metric))
	for k, v := range s.Labels {
		msg = appendTagBytes(msg, 1, marshalLabel(k, v))
	}
	msg = appendTagBytes(msg, 2, marshalSample(s.Value, s.At.UnixMilli()))
	return msg
}

func marshalLabel(name, value string) []byte {
	var msg []byte
	msg = appendTagBytes(msg, 1, []byte(name))
	msg = appendTagBytes(msg, 2, []byte(value))
	return msg
}

func marshalSample(value float64, timestampMs int64) []byte {
	var msg []byte
	msg = append(msg, byte((1<<3)|1)) // field 1, wire type 1 (64-bit)
	var buf [8]byte
	binary.LittleEndian.PutUint64(buf[:], math.Float64bits(value))
	msg = append(msg, buf[:]...)
	msg = appendVarint(msg, (2<<3)|0) // field 2, wire type 0
	msg = appendVarint(msg, uint64(timestampMs))
	return msg
}

func appendTagBytes(dst []byte, field int, payload []byte) []byte {
	dst = appendVarint(dst, uint64((field<<3)|2))
	dst = appendVarint(dst, uint64(len(payload)))
	return append(dst, payload...)
}

func appendVarint(dst []byte, v uint64) []byte {
	for v >= 0x80 {
		dst = append(dst, byte(v)|0x80)
		v >>= 7
	}
	return append(dst, byte(v))
}
