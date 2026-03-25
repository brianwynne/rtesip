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

export interface CallState {
  state: "idle" | "calling" | "ringing" | "incoming" | "connected";
  destination?: string;
  connectedAt?: number;  // server epoch timestamp
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
