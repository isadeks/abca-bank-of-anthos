/*
 * Copyright 2025, Google LLC.
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */
package anthos.samples.bankofanthos.transactionhistory;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.ParameterizedTypeReference;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpMethod;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestTemplate;

/**
 * Reads a user's contacts from the contacts service.
 */
@Component
public class ContactsClient {

    private final RestTemplate restTemplate = new RestTemplate();
    private final String contactsAddr;

    /**
     * Constructor.
     *
     * @param contactsAddr host:port of the contacts service
     */
    public ContactsClient(
            @Value("${CONTACTS_API_ADDR:contacts:8080}")
            final String contactsAddr) {
        this.contactsAddr = contactsAddr;
    }

    /**
     * Returns the contacts of the user marked as favourite.
     *
     * @param username    the user whose contacts to read
     * @param bearerToken the raw JWT of the user, forwarded to the service
     * @return the favourite contacts, each with label, account_num and
     *         routing_num
     */
    public List<Map<String, Object>> getFavourites(final String username,
            final String bearerToken) {
        HttpHeaders headers = new HttpHeaders();
        headers.set("Authorization", "Bearer " + bearerToken);
        List<Map<String, Object>> all = restTemplate.exchange(
            "http://" + contactsAddr + "/contacts/" + username,
            HttpMethod.GET, new HttpEntity<>(headers),
            new ParameterizedTypeReference<List<Map<String, Object>>>() { })
            .getBody();
        List<Map<String, Object>> favourites = new ArrayList<>();
        if (all != null) {
            for (Map<String, Object> contact : all) {
                if (Boolean.TRUE.equals(contact.get("is_favorite"))) {
                    favourites.add(contact);
                }
            }
        }
        return favourites;
    }
}
