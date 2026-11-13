/**
 * Readable aliases for the types generated from `api/openapi.yaml`.
 *
 * Do not define API types by hand: change `api/openapi.yaml` and run `npm run gen:api`.
 */
import type { components } from './schema';

type Schemas = components['schemas'];

export type Item = Schemas['Item'];
export type ItemId = Schemas['ItemId'];
export type ItemSource = Schemas['ItemSource'];
export type NewItem = Schemas['NewItem'];
export type NewItemBatch = Schemas['NewItemBatch'];
export type ItemList = Schemas['ItemList'];
export type Recommendation = Schemas['Recommendation'];
export type RecommendationRequest = Schemas['RecommendationRequest'];
export type RecommendationResponse = Schemas['RecommendationResponse'];
export type ErrorCode = Schemas['ErrorCode'];
export type FieldError = Schemas['FieldError'];
export type ErrorResponse = Schemas['ErrorResponse'];
