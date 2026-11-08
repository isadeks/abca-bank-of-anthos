/*
 * Copyright 2026, Google LLC.
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

package anthos.samples.bankofanthos.balancereader;

import jakarta.persistence.EntityManagerFactory;
import javax.sql.DataSource;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.data.jpa.repository.config.EnableJpaRepositories;
import org.springframework.jdbc.datasource.DriverManagerDataSource;
import org.springframework.orm.jpa.JpaTransactionManager;
import org.springframework.orm.jpa.LocalContainerEntityManagerFactoryBean;
import org.springframework.orm.jpa.vendor.HibernateJpaVendorAdapter;
import org.springframework.transaction.PlatformTransactionManager;
import org.springframework.transaction.annotation.EnableTransactionManagement;

/**
 * Wires the service's JPA entity and repository to the real ledger database.
 *
 * The connection comes from the standard Spring Boot environment variables
 * SPRING_DATASOURCE_URL, SPRING_DATASOURCE_USERNAME and
 * SPRING_DATASOURCE_PASSWORD, which CI points at the ledger-db image.
 */
@Configuration
@EnableJpaRepositories(basePackageClasses = TransactionRepository.class)
@EnableTransactionManagement
class LedgerDbTestConfig {

    @Bean
    DataSource dataSource() {
        String url = System.getenv("SPRING_DATASOURCE_URL");
        if (url == null || url.isEmpty()) {
            throw new IllegalStateException(
                "SPRING_DATASOURCE_URL must point at the ledger database");
        }
        DriverManagerDataSource dataSource = new DriverManagerDataSource(
            url,
            System.getenv("SPRING_DATASOURCE_USERNAME"),
            System.getenv("SPRING_DATASOURCE_PASSWORD"));
        dataSource.setDriverClassName("org.postgresql.Driver");
        return dataSource;
    }

    @Bean
    LocalContainerEntityManagerFactoryBean entityManagerFactory(
            DataSource dataSource) {
        LocalContainerEntityManagerFactoryBean factory =
            new LocalContainerEntityManagerFactoryBean();
        factory.setDataSource(dataSource);
        factory.setPackagesToScan(Transaction.class.getPackageName());
        factory.setJpaVendorAdapter(new HibernateJpaVendorAdapter());
        return factory;
    }

    @Bean
    PlatformTransactionManager transactionManager(
            EntityManagerFactory entityManagerFactory) {
        return new JpaTransactionManager(entityManagerFactory);
    }
}
