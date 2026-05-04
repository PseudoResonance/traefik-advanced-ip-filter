// Package advancedipfilter Traefik Plugin.
package advancedipfilter

import (
	"context"
	"errors"
	"fmt"
	"net/http"
	"net/netip"
	"slices"
	"strings"
)

// Config the plugin configuration.
type Config struct {
	Debug       bool       `json:"debug,omitempty"`
	SourceRange []string   `json:"sourceRange,omitempty"` // DONE
	Denylist    bool       `json:"denylist,omitempty"`    // DONE
	IpStrategy  IpStrategy `json:"ipStrategy,omitempty"`
}

type ConfigParsed struct {
	SourceRange []IpOrNet
	Denylist    bool
	IpStrategy  IpStrategyParsed
}

type IpStrategy struct {
	Depth           int      `json:"depth,omitempty"`
	Header          string   `json:"header,omitempty"`
	IsTrustedHeader string   `json:"isTrustedHeader,omitempty"`
	SourceFallback  bool     `json:"sourceFallback,omitempty"`
	ExcludedIps     []string `json:"excludedIPs,omitempty"`
	Ipv6Subnet      int      `json:"ipv6Subnet,omitempty"`
}

type IpStrategyParsed struct {
	Depth           int
	Header          string
	IsTrustedHeader string
	SourceFallback  bool
	ExcludedIps     []netip.Addr
	Ipv6Subnet      int
}

// CreateConfig creates the default plugin configuration.
func CreateConfig() *Config {
	return &Config{
		Debug:       false,
		SourceRange: []string{},
		Denylist:    false,
		IpStrategy: IpStrategy{
			Depth:           0,
			Header:          "X-Forwarded-For",
			IsTrustedHeader: "X-Is-Trusted",
			SourceFallback:  true,
			ExcludedIps:     []string{},
		},
	}
}

type IpOrNet struct {
	ip  netip.Addr
	net netip.Prefix
	raw string
}

// AdvancedIpFilter is a plugin that filters incoming requests by IPs.
type AdvancedIpFilter struct {
	next   http.Handler
	name   string
	debug  bool
	config ConfigParsed
}

// New created a new plugin.
func New(_ context.Context, next http.Handler, config *Config, name string) (http.Handler, error) {
	advancedIpFilter := &AdvancedIpFilter{
		next:  next,
		name:  name,
		debug: config.Debug,
		config: ConfigParsed{
			SourceRange: []IpOrNet{},
			Denylist:    config.Denylist,
			IpStrategy: IpStrategyParsed{
				Depth:           config.IpStrategy.Depth,
				Header:          config.IpStrategy.Header,
				IsTrustedHeader: config.IpStrategy.IsTrustedHeader,
				SourceFallback:  config.IpStrategy.SourceFallback,
				ExcludedIps:     []netip.Addr{},
				Ipv6Subnet:      config.IpStrategy.Ipv6Subnet,
			},
		},
	}

	if advancedIpFilter.debug {
		fmt.Printf("DEBUG: AdvancedIpFilter: Debug printing enabled!\n")
	}

	if config.SourceRange != nil {
		for _, v := range config.SourceRange {
			ip, errIp := netip.ParseAddr(v)
			prefix, errPrefix := netip.ParsePrefix(v)
			if errIp != nil && errPrefix != nil {
				return nil, fmt.Errorf("Invalid IP/CIDR in sourceRange [%s]\n", v)
			}
			if advancedIpFilter.debug {
				if prefix.IsValid() {
					fmt.Printf("DEBUG: AdvancedIpFilter: IP/CIDR [%s] parsed as CIDR [%s]\n", v, prefix.String())
				} else if ip.IsValid() {
					fmt.Printf("DEBUG: AdvancedIpFilter: IP/CIDR [%s] parsed as IP [%s]\n", v, ip.String())
				}
			}
			advancedIpFilter.config.SourceRange = append(advancedIpFilter.config.SourceRange, IpOrNet{
				ip:  ip,
				net: prefix,
				raw: v,
			})
		}
	} else {
		return nil, errors.New("IP sourceRange was not configured!")
	}

	if config.IpStrategy.ExcludedIps != nil {
		for _, v := range config.IpStrategy.ExcludedIps {
			ip, err := netip.ParseAddr(v)
			if err != nil {
				return nil, fmt.Errorf("Invalid IP in ipStrategy.excludedIps [%s]", v)
			}
			advancedIpFilter.config.IpStrategy.ExcludedIps = append(advancedIpFilter.config.IpStrategy.ExcludedIps, ip)
		}
	}

	return advancedIpFilter, nil
}

func (r *AdvancedIpFilter) ServeHTTP(rw http.ResponseWriter, req *http.Request) {
	testIp := netip.Addr{}
	if len(r.config.IpStrategy.Header) > 0 {
		headerValue := req.Header.Get(r.config.IpStrategy.Header)
		ip := r.GetForwardedIp(headerValue)
		if ip.IsValid() {
			testIp = ip
		} else if !r.config.IpStrategy.SourceFallback {
			if r.debug {
				fmt.Printf("DEBUG: AdvancedIpFilter: Forbidden: IP header [%s]=[%s] did not contain any usable IP and source address fallback was disabled\n", r.config.IpStrategy.Header, headerValue)
			}
			http.Error(rw, "Forbidden", http.StatusForbidden)
			return
		}
	} else if !r.config.IpStrategy.SourceFallback {
		if r.debug {
			fmt.Printf("DEBUG: AdvancedIpFilter: Forbidden: IP header [%s] was empty and source address fallback was disabled\n", r.config.IpStrategy.Header)
		}
		http.Error(rw, "Forbidden", http.StatusForbidden)
		return
	}
	if !testIp.IsValid() {
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
		testIp = addrPort.Addr()
	}

	testIp = r.TruncateIpv6(testIp)

	if r.IpInSource(testIp) != r.config.Denylist {
		if r.debug {
			fmt.Printf("DEBUG: AdvancedIpFilter: IP allowed [%s]\n", testIp.String())
		}
		r.next.ServeHTTP(rw, req)
		return
	} else {
		if r.debug {
			fmt.Printf("DEBUG: AdvancedIpFilter: IP denied [%s]\n", testIp.String())
		}
		http.Error(rw, "Forbidden", http.StatusForbidden)
		return
	}
}

func (r *AdvancedIpFilter) TruncateIpv6(testIp netip.Addr) netip.Addr {
	if !testIp.Is6() || r.config.IpStrategy.Ipv6Subnet <= 0 {
		return testIp
	}

	res, err := testIp.Prefix(r.config.IpStrategy.Ipv6Subnet)
	if err != nil {
		fmt.Printf("DEBUG: AdvancedIpFilter: Error while truncating IP [%s] with subnet of [%d]: [%v]\n", testIp.String(), r.config.IpStrategy.Ipv6Subnet, err)
		return testIp
	}

	if r.debug {
		fmt.Printf("DEBUG: AdvancedIpFilter: IP [%s] truncated to [%s] by ipStrategy.ipv6Subnet of [%d]\n", testIp.String(), res.String(), r.config.IpStrategy.Ipv6Subnet)
	}
	return testIp
}

func (r *AdvancedIpFilter) IpInSource(testIp netip.Addr) bool {
	for _, v := range r.config.SourceRange {
		if v.ip.IsValid() {
			if v.ip == testIp {
				if r.debug {
					fmt.Printf("DEBUG: AdvancedIpFilter: Test IP [%s] matched by IP against [%s]\n", testIp.String(), v.raw)
				}
				return true
			}
		} else if v.net.IsValid() {
			if v.net.Contains(testIp) {
				if r.debug {
					fmt.Printf("DEBUG: AdvancedIpFilter: Test IP [%s] matched by CIDR against [%s]\n", testIp.String(), v.raw)
				}
				return true
			}
		}
	}
	if r.debug {
		fmt.Printf("DEBUG: AdvancedIpFilter: Test IP [%s] did not match any IPs/CIDRs\n", testIp.String())
	}
	return false
}

func (r *AdvancedIpFilter) IsTrusted(req *http.Request) bool {
	if len(r.config.IpStrategy.IsTrustedHeader) > 0 {
		valueRaw := req.Header.Get(r.config.IpStrategy.IsTrustedHeader)
		value := strings.ToLower(valueRaw)
		res := value == "yes" ||
			value == "true" ||
			value == "y" ||
			value == "t" ||
			value == "trusted" ||
			value == "trust"
		if r.debug {
			fmt.Printf("DEBUG: AdvancedIpFilter: isTrustedHeader [%s]=[%s] Result=%t\n", r.config.IpStrategy.IsTrustedHeader, valueRaw, res)
		}
		return res
	} else {
		if r.debug {
			fmt.Printf("DEBUG: AdvancedIpFilter: isTrustedHeader is blank, so IP is trusted by default\n")
		}
		// Trust by default if the header name is blank
		return true
	}
}

func (r *AdvancedIpFilter) IsIpExcluded(ip netip.Addr) bool {
	if !ip.IsValid() {
		return true
	}

	return slices.Contains(r.config.IpStrategy.ExcludedIps, ip)
}

func (r *AdvancedIpFilter) GetForwardedIp(header string) netip.Addr {
	s := strings.Split(header, ",")
	// depth is ignored if its value is less than or equal to 0.
	if r.config.IpStrategy.Depth <= 0 {
		// If depth is specified, excludedIPs is ignored.
		// Thus, excludedIPs is used only if depth isn't specified
		if len(r.config.IpStrategy.ExcludedIps) == 0 {
			return netip.Addr{}
		} else {
			for _, v := range slices.Backward(s) {
				v = strings.TrimSpace(v)
				ip, err := netip.ParseAddr(v)
				if err != nil {
					if r.debug {
						fmt.Printf("DEBUG: AdvancedIpFilter: Error parsing IP [%s] in header [%s]\n", v, header)
					}
					continue
				}
				if !r.IsIpExcluded(ip) {
					// First non excluded IP is chosen
					return ip
				}
			}
			return netip.Addr{}
		}
	}

	// If depth is greater than the total number of IPs in X-Forwarded-For, then the client IP will be empty.
	if r.config.IpStrategy.Depth > len(s) {
		return netip.Addr{}
	}

	strIp := strings.TrimSpace(s[len(s)-r.config.IpStrategy.Depth])
	ip, err := netip.ParseAddr(strIp)
	if err != nil {
		if r.debug {
			fmt.Printf("DEBUG: AdvancedIpFilter: Error parsing IP [%s] in header [%s]\n", strIp, header)
			return netip.Addr{}
		}
	}
	if r.debug {
		fmt.Printf("DEBUG: AdvancedIpFilter: Found IP [%s] at depth [%d] in header [%s]\n", ip.String(), r.config.IpStrategy.Depth, header)
	}
	return ip
}
