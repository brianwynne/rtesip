export interface SipAccount {
  username: string;
  password: string;
  registrar: string;
  realm: string;
  proxy: string;
  proxy2: string;
  transport: "tls" | "tcp" | "udp";
  keying: number;
  reg_timeout: number;
}

export interface Contact {
  id: number;
  name: string;
  address: string;
  type: "sip" | "isdn" | "pstn";
  quickDial?: boolean;
}

export interface CallQuality {
  tx_packets?: number;
  tx_lost?: number;
  tx_loss_pct?: number;
  tx_bitrate?: number;
  tx_bitrate_ip?: number;
  rx_packets?: number;
  rx_lost?: number;
  rx_loss_pct?: number;
  rx_bitrate?: number;
  rx_bitrate_ip?: number;
  rx_jitter_avg?: number;
  rx_jitter_max?: number;
  rx_jitter_last?: number;
  tx_jitter_avg?: number;
  tx_jitter_max?: number;
  tx_jitter_last?: number;
  rtt_avg?: number;
  rtt_last?: number;
}

export interface CallState {
  state: "idle" | "calling" | "ringing" | "incoming" | "connected";
  destination?: string;
  connectedAt?: number;  // server epoch timestamp
  codec?: string;
  srtpActive?: boolean;
  srtpSuite?: string;
  quality?: CallQuality;
}

export interface AccountStatus {
  id: string;
  status: number;
  registered: boolean;
}

export interface VolumeState {
  cl: number;
  cr: number;
  clink: boolean;
  pl: number;
  pr: number;
  plink: boolean;
}

export interface SystemStatus {
  cpu_temp: string;
  uptime_seconds: number;
  hostname: string;
  serial: string;
  model: string;
}

export interface WsMessage {
  event: string;
  [key: string]: unknown;
}
