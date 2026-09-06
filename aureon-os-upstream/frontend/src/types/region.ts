/**
 * Region type definition
 */
export interface Region {
  id: string;
  name: string;
  population: number;
  area: number; // km²
  emotionalProfile?: any;
  [key: string]: any;
}
