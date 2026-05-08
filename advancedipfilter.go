// Package traefik_advanced_ip_filter Traefik Plugin.
package traefik_advanced_ip_filter //nolint:revive,stylecheck

import (
	"context"
	"errors"
	"fmt"
	"net/http"
	"net/netip"
	"strings"
)

// Config the plugin configuration.
type Config struct {
	Debug       bool        `json:"debug"`
	SourceRange []string    `json:"sourceRange"`
	Denylist    bool        `json:"denylist"`
	IPStrategy  *ipStrategy `json:"ipStrategy"`
}

type configParsed struct {
	SourceRange []ipOrNet
	Denylist    bool
	IPStrategy  *ipStrategyParsed
}

type ipStrategy struct {
	Depth           int      `json:"depth"`
	Header          string   `json:"header"`
	IsTrustedHeader string   `json:"isTrustedHeader"`
	SourceFallback  bool     `json:"sourceFallback"`
	ExcludedIps     []string `json:"excludedIPs"`
	Ipv6Subnet      int      `json:"ipv6Subnet"`
}

type ipStrategyParsed struct {
	Depth           int
	Header          string
	IsTrustedHeader string
	SourceFallback  bool
	ExcludedIps     []ipOrNet
	Ipv6Subnet      int
}

// CreateConfig creates the default plugin configuration.
func CreateConfig() *Config {
	return &Config{
		Debug:       false,
		SourceRange: []string{},
		Denylist:    false,
		IPStrategy: &ipStrategy{
			Depth:           0,
			Header:          "X-Forwarded-For",
			IsTrustedHeader: "X-Is-Trusted",
			SourceFallback:  true,
			ExcludedIps:     []string{},
		},
	}
}

type ipOrNet struct {
	ip  netip.Addr
	net netip.Prefix
	raw string
}

// AdvancedIPFilter is a plugin that filters incoming requests by IPs.
type AdvancedIPFilter struct {
	next   http.Handler
	name   string
	debug  bool
	config configParsed
}

// New created a new plugin.
func New(_ context.Context, next http.Handler, config *Config, name string) (http.Handler, error) {
	advancedIPFilter := &AdvancedIPFilter{
		next:  next,
		name:  name,
		debug: config.Debug,
		config: configParsed{
			SourceRange: []ipOrNet{},
			Denylist:    config.Denylist,
			IPStrategy: &ipStrategyParsed{
				Depth:           config.IPStrategy.Depth,
				Header:          config.IPStrategy.Header,
				IsTrustedHeader: config.IPStrategy.IsTrustedHeader,
				SourceFallback:  config.IPStrategy.SourceFallback,
				ExcludedIps:     []ipOrNet{},
				Ipv6Subnet:      config.IPStrategy.Ipv6Subnet,
			},
		},
	}

	if advancedIPFilter.debug {
		fmt.Printf("DEBUG: AdvancedIpFilter: Debug printing enabled!\n")
	}

	if config.SourceRange != nil {
		for _, v := range config.SourceRange {
			ipnet, err := advancedIPFilter.parseIPOrNet(v)
			if err != nil {
				return nil, fmt.Errorf("error parsing sourceRange [%w]", err)
			}
			advancedIPFilter.config.SourceRange = append(advancedIPFilter.config.SourceRange, *ipnet)
		}
	} else {
		return nil, errors.New("IP sourceRange was not configured!") //nolint:revive,stylecheck
	}

	if config.IPStrategy.ExcludedIps != nil {
		for _, v := range config.IPStrategy.ExcludedIps {
			ipnet, err := advancedIPFilter.parseIPOrNet(v)
			if err != nil {
				return nil, fmt.Errorf("error parsing ipStrategy.excludedIps [%w]", err)
			}
			advancedIPFilter.config.IPStrategy.ExcludedIps = append(advancedIPFilter.config.IPStrategy.ExcludedIps, *ipnet)
		}
	}

	return advancedIPFilter, nil
}

//nolint:gocognit
func (r *AdvancedIPFilter) ServeHTTP(rw http.ResponseWriter, req *http.Request) {
	testIP := netip.Addr{}
	if len(r.config.IPStrategy.Header) > 0 && r.isTrusted(req) {
		headerValue := req.Header.Get(r.config.IPStrategy.Header)
		ip := r.getForwardedIP(headerValue)
		if ip.IsValid() {
			testIP = ip
		} else if !r.config.IPStrategy.SourceFallback {
			if r.debug {
				fmt.Printf("DEBUG: AdvancedIpFilter: Forbidden: IP header [%s]=[%s] did not contain any usable IP and source address fallback was disabled\n", r.config.IPStrategy.Header, headerValue)
			}
			http.Error(rw, "Forbidden", http.StatusForbidden)
			return
		}
	} else if !r.config.IPStrategy.SourceFallback {
		if r.debug {
			fmt.Printf("DEBUG: AdvancedIpFilter: Forbidden: IP header [%s] was empty and source address fallback was disabled\n", r.config.IPStrategy.Header)
		}
		http.Error(rw, "Forbidden", http.StatusForbidden)
		return
	}
	if !testIP.IsValid() {
		if r.debug {
			if len(r.config.IPStrategy.Header) > 0 && r.isTrusted(req) {
				fmt.Printf("DEBUG: AdvancedIpFilter: Unable to fetch IP from header, falling back to source IP\n")
			} else {
				fmt.Printf("DEBUG: AdvancedIpFilter: Using source IP\n")
			}
		}
		addrPort, err := netip.ParseAddrPort(req.RemoteAddr)
		if err != nil {
			if r.debug {
				fmt.Printf("DEBUG: AdvancedIpFilter: Internal Server Error: Address [%s] could not be parsed into address and port\n", req.RemoteAddr)
			}
			http.Error(rw, "Unknown source", http.StatusInternalServerError)
			return
		}
		if !addrPort.Addr().IsValid() {
			if r.debug {
				fmt.Printf("DEBUG: AdvancedIpFilter: Internal Server Error: Address [%s] could not be parsed into a valid IP\n", req.RemoteAddr)
			}
			http.Error(rw, "Unknown source", http.StatusInternalServerError)
			return
		}
		testIP = addrPort.Addr()
	}

	testIP = r.truncateIpv6(testIP)

	if r.ipInSource(testIP) != r.config.Denylist {
		if r.debug {
			fmt.Printf("DEBUG: AdvancedIpFilter: IP allowed [%s]\n", testIP.String())
		}
		r.next.ServeHTTP(rw, req)
	} else {
		if r.debug {
			fmt.Printf("DEBUG: AdvancedIpFilter: IP denied [%s]\n", testIP.String())
		}
		http.Error(rw, "Forbidden", http.StatusForbidden)
	}
}

func (r *AdvancedIPFilter) parseIPOrNet(input string) (*ipOrNet, error) {
	ip, errIP := netip.ParseAddr(input)
	prefix, errPrefix := netip.ParsePrefix(input)
	if errIP != nil && errPrefix != nil {
		return nil, fmt.Errorf("invalid IP/CIDR [%s]", input)
	}
	if r.debug {
		if prefix.IsValid() {
			fmt.Printf("DEBUG: AdvancedIpFilter: IP/CIDR [%s] parsed as CIDR [%s]\n", input, prefix.String())
		} else if ip.IsValid() {
			fmt.Printf("DEBUG: AdvancedIpFilter: IP/CIDR [%s] parsed as IP [%s]\n", input, ip.String())
		}
	}
	return &ipOrNet{
		ip:  ip,
		net: prefix,
		raw: input,
	}, nil
}

func (r *AdvancedIPFilter) truncateIpv6(testIP netip.Addr) netip.Addr {
	if !testIP.Is6() || r.config.IPStrategy.Ipv6Subnet <= 0 {
		return testIP
	}

	res, err := testIP.Prefix(r.config.IPStrategy.Ipv6Subnet)
	if err != nil {
		fmt.Printf("DEBUG: AdvancedIpFilter: Error while truncating IP [%s] with subnet of [%d]: [%v]\n", testIP.String(), r.config.IPStrategy.Ipv6Subnet, err)
		return testIP
	}

	if r.debug {
		fmt.Printf("DEBUG: AdvancedIpFilter: IP [%s] truncated to [%s] by ipStrategy.ipv6Subnet of [%d]\n", testIP.String(), res.String(), r.config.IPStrategy.Ipv6Subnet)
	}
	return res.Addr()
}

func (r *AdvancedIPFilter) ipInSource(testIP netip.Addr) bool {
	for _, v := range r.config.SourceRange {
		if v.ip.IsValid() {
			if v.ip == testIP {
				if r.debug {
					fmt.Printf("DEBUG: AdvancedIpFilter: Test IP [%s] matched by IP against [%s]\n", testIP.String(), v.raw)
				}
				return true
			}
		} else if v.net.IsValid() {
			if v.net.Contains(testIP) {
				if r.debug {
					fmt.Printf("DEBUG: AdvancedIpFilter: Test IP [%s] matched by CIDR against [%s]\n", testIP.String(), v.raw)
				}
				return true
			}
		}
	}
	if r.debug {
		fmt.Printf("DEBUG: AdvancedIpFilter: Test IP [%s] did not match any IPs/CIDRs\n", testIP.String())
	}
	return false
}

func (r *AdvancedIPFilter) isTrusted(req *http.Request) bool {
	if len(r.config.IPStrategy.IsTrustedHeader) > 0 {
		valueRaw := req.Header.Get(r.config.IPStrategy.IsTrustedHeader)
		value := strings.ToLower(valueRaw)
		res := value == "yes" ||
			value == "true" ||
			value == "y" ||
			value == "t" ||
			value == "trusted" ||
			value == "trust"
		if r.debug {
			fmt.Printf("DEBUG: AdvancedIpFilter: isTrustedHeader [%s]=[%s] Result=%t\n", r.config.IPStrategy.IsTrustedHeader, valueRaw, res)
		}
		return res
	}
	if r.debug {
		fmt.Printf("DEBUG: AdvancedIpFilter: isTrustedHeader is blank, so IP is trusted by default\n")
	}
	// Trust by default if the header name is blank
	return true
}

func (r *AdvancedIPFilter) isIPExcluded(ip netip.Addr) bool {
	if !ip.IsValid() {
		return true
	}

	for _, v := range r.config.IPStrategy.ExcludedIps {
		if v.ip.IsValid() {
			if v.ip == ip {
				if r.debug {
					fmt.Printf("DEBUG: AdvancedIpFilter: Test IP [%s] excluded by matching by IP against [%s]\n", ip.String(), v.raw)
				}
				return true
			}
		} else if v.net.IsValid() {
			if v.net.Contains(ip) {
				if r.debug {
					fmt.Printf("DEBUG: AdvancedIpFilter: Test IP [%s] excluded by matching by CIDR against [%s]\n", ip.String(), v.raw)
				}
				return true
			}
		}
	}
	return false
}

func (r *AdvancedIPFilter) getForwardedIP(header string) netip.Addr {
	s := strings.Split(header, ",")
	// depth is ignored if its value is less than or equal to 0.
	if r.config.IPStrategy.Depth <= 0 {
		if r.debug {
			fmt.Printf("DEBUG: AdvancedIpFilter: Searching for IP in header via exclusion\n")
		}
		// If depth is specified, excludedIPs is ignored.
		// Thus, excludedIPs is used only if depth isn't specified
		if len(r.config.IPStrategy.ExcludedIps) == 0 {
			return netip.Addr{}
		}
		for i := range s {
			v := s[len(s)-i-1]
			v = strings.TrimSpace(v)
			ip, err := netip.ParseAddr(v)
			if err != nil {
				if r.debug {
					fmt.Printf("DEBUG: AdvancedIpFilter: Error parsing IP [%s] in header [%s]\n", v, header)
				}
				continue
			}
			if !r.isIPExcluded(ip) {
				// First non excluded IP is chosen
				return ip
			}
		}
		return netip.Addr{}
	}

	if r.debug {
		fmt.Printf("DEBUG: AdvancedIpFilter: Searching for IP in header via depth\n")
	}

	// If depth is greater than the total number of IPs in X-Forwarded-For, then the client IP will be empty.
	if r.config.IPStrategy.Depth > len(s) {
		return netip.Addr{}
	}

	strIP := strings.TrimSpace(s[len(s)-r.config.IPStrategy.Depth])
	ip, err := netip.ParseAddr(strIP)
	if err != nil {
		if r.debug {
			fmt.Printf("DEBUG: AdvancedIpFilter: Error parsing IP [%s] in header [%s]\n", strIP, header)
			return netip.Addr{}
		}
	}
	if r.debug {
		fmt.Printf("DEBUG: AdvancedIpFilter: Found IP [%s] at depth [%d] in header [%s]\n", ip.String(), r.config.IPStrategy.Depth, header)
	}
	return ip
}
