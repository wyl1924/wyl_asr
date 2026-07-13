export interface HotwordConfig {
  label: string;
  words: string[];
}

export interface HotwordsConfig {
  government: HotwordConfig;
  education: HotwordConfig;
  oil: HotwordConfig;
  petrochemical: HotwordConfig;
  enterprise: HotwordConfig;
}

export type IndustryType = keyof HotwordsConfig;