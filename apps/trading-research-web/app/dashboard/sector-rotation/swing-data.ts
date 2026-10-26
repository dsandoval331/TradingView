import 'server-only';
import type {SwingSuggestion} from './swing-trades';
/** Entry logic is pending. Connect this loader to recorded suggestions after rules are supplied.
 * Authenticated tracker routes call this adapter; never put private trade records in source or a public client bundle. */
export async function loadSwingSuggestions():Promise<readonly SwingSuggestion[]>{return [];}
