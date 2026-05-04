package advancedipfilter_test

import (
	"context"
	"net/http"
	"net/http/httptest"
	"strconv"
	"testing"

	plugin "github.com/PseudoResonance/traefik-advanced-ip-filter"
)

func TestNew(t *testing.T) {
	cfg := plugin.CreateConfig()
	cfg.SourceRange = []string{"10.0.0.0/8", "fd00::/8"}

	ctx := context.Background()
	testCases := []struct {
		desc         string
		ip           string
		expectedFail bool
	}{
		{
			desc:         "Test matched IP",
			ip:           "10.1.1.1:1",
			expectedFail: false,
		},
		{
			desc:         "Test matched IPv6",
			ip:           "[fd7e:a346:9d5b:abed:13c8:cc73:abf7:e607]:1",
			expectedFail: false,
		},
		{
			desc:         "Test not matched IP",
			ip:           "192.168.1.1:1",
			expectedFail: true,
		},
		{
			desc:         "Test not matched IPv6",
			ip:           "[54fc:7088:0c85:9cdb:6b07:24d8:8229:e46c]:1",
			expectedFail: true,
		},
	}
	for _, test := range testCases {
		t.Run(test.desc, func(t *testing.T) {
			recorder := httptest.NewRecorder()

			next := http.HandlerFunc(func(rw http.ResponseWriter, _ *http.Request) {
				rw.WriteHeader(http.StatusOK)
			})

			handler, err := plugin.New(ctx, next, cfg, "advancedipfilter")
			if err != nil {
				t.Fatal(err)
			}

			req, err := http.NewRequestWithContext(ctx, http.MethodGet, "http://localhost", nil)
			if err != nil {
				t.Fatal(err)
			}
			req.RemoteAddr = test.ip

			handler.ServeHTTP(recorder, req)

			if (recorder.Result().StatusCode == http.StatusOK) == test.expectedFail {
				t.Errorf("invalid status: %v, expected failure: %t", strconv.Itoa(recorder.Result().StatusCode), test.expectedFail)
				return
			}
		})
	}
}
