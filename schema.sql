PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS departments(id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE);
CREATE TABLE IF NOT EXISTS roles(id INTEGER PRIMARY KEY, code TEXT NOT NULL UNIQUE, name TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS users(
 id INTEGER PRIMARY KEY, login TEXT NOT NULL UNIQUE, password_hash TEXT NOT NULL, name TEXT NOT NULL,
 role_id INTEGER NOT NULL REFERENCES roles, department_id INTEGER NOT NULL REFERENCES departments, shift TEXT
);
CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users ON DELETE CASCADE, expires INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS products(
 id INTEGER PRIMARY KEY, code TEXT NOT NULL UNIQUE, name TEXT NOT NULL, type TEXT NOT NULL,
 format TEXT NOT NULL, collection TEXT NOT NULL, surface TEXT NOT NULL,
 status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active','archived'))
);
CREATE TABLE IF NOT EXISTS materials(id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE, category TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS raw_lots(
 id INTEGER PRIMARY KEY, code TEXT NOT NULL UNIQUE, supplier_code TEXT NOT NULL, material_id INTEGER NOT NULL REFERENCES materials,
 supplier TEXT NOT NULL, received TEXT NOT NULL, quantity REAL NOT NULL CHECK(quantity>0),
 unit TEXT NOT NULL DEFAULT 'кг', location TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending'
 CHECK(status IN ('pending','released','blocked'))
);
CREATE TABLE IF NOT EXISTS equipment(
 id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE, kind TEXT NOT NULL, line TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'ready'
);
CREATE TABLE IF NOT EXISTS equipment_programs(
 id INTEGER PRIMARY KEY, equipment_id INTEGER NOT NULL REFERENCES equipment, name TEXT NOT NULL,
 temperature REAL, duration REAL CHECK(duration>0), pressure REAL CHECK(pressure>=0), notes TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS recipes(
 id INTEGER PRIMARY KEY, product_id INTEGER NOT NULL REFERENCES products, kind TEXT NOT NULL CHECK(kind IN ('mass','glaze')),
 version INTEGER NOT NULL CHECK(version>0), status TEXT NOT NULL DEFAULT 'draft'
 CHECK(status IN ('draft','review','active','archived')), author_id INTEGER NOT NULL REFERENCES users,
 created TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, notes TEXT NOT NULL DEFAULT '', UNIQUE(product_id,kind,version)
);
CREATE UNIQUE INDEX IF NOT EXISTS active_recipe ON recipes(product_id,kind) WHERE status='active';
CREATE TABLE IF NOT EXISTS recipe_items(
 id INTEGER PRIMARY KEY, recipe_id INTEGER NOT NULL REFERENCES recipes, material_id INTEGER NOT NULL REFERENCES materials,
 basis_points INTEGER NOT NULL CHECK(typeof(basis_points)='integer' AND basis_points BETWEEN 1 AND 10000),
 position INTEGER NOT NULL CHECK(position>0), tolerance REAL NOT NULL DEFAULT 0 CHECK(tolerance>=0),
 UNIQUE(recipe_id,position), UNIQUE(recipe_id,material_id)
);
CREATE TRIGGER IF NOT EXISTS no_active_insert BEFORE INSERT ON recipes WHEN NEW.status='active'
 BEGIN SELECT RAISE(ABORT,'recipe_create_draft'); END;
CREATE TRIGGER IF NOT EXISTS recipe_total BEFORE UPDATE OF status ON recipes WHEN NEW.status='active' AND
 (SELECT COALESCE(SUM(basis_points),0) FROM recipe_items WHERE recipe_id=NEW.id)<>10000
 BEGIN SELECT RAISE(ABORT,'recipe_total'); END;
CREATE TRIGGER IF NOT EXISTS recipe_item_insert BEFORE INSERT ON recipe_items WHEN EXISTS(
 SELECT 1 FROM recipes WHERE id=NEW.recipe_id AND status IN ('active','archived'))
 BEGIN SELECT RAISE(ABORT,'recipe_locked'); END;
CREATE TRIGGER IF NOT EXISTS recipe_item_update BEFORE UPDATE ON recipe_items WHEN EXISTS(
 SELECT 1 FROM recipes WHERE id IN (OLD.recipe_id,NEW.recipe_id) AND status IN ('active','archived'))
 BEGIN SELECT RAISE(ABORT,'recipe_locked'); END;
CREATE TRIGGER IF NOT EXISTS recipe_item_delete BEFORE DELETE ON recipe_items WHEN EXISTS(
 SELECT 1 FROM recipes WHERE id=OLD.recipe_id AND status IN ('active','archived'))
 BEGIN SELECT RAISE(ABORT,'recipe_locked'); END;
CREATE TRIGGER IF NOT EXISTS recipe_status_locked BEFORE UPDATE ON recipes
 WHEN (OLD.status='active' AND NEW.status NOT IN ('active','archived'))
 OR (OLD.status='archived' AND NEW.status<>'archived')
 OR (OLD.status IN ('active','archived') AND
     (NEW.product_id<>OLD.product_id OR NEW.kind<>OLD.kind OR NEW.version<>OLD.version))
 BEGIN SELECT RAISE(ABORT,'recipe_locked'); END;
CREATE TABLE IF NOT EXISTS tech_cards(
 id INTEGER PRIMARY KEY, product_id INTEGER NOT NULL REFERENCES products, version INTEGER NOT NULL CHECK(version>0),
 status TEXT NOT NULL DEFAULT 'draft' CHECK(status IN ('draft','active','archived')), name TEXT NOT NULL,
 UNIQUE(product_id,version)
);
CREATE UNIQUE INDEX IF NOT EXISTS active_card ON tech_cards(product_id) WHERE status='active';
CREATE TABLE IF NOT EXISTS card_steps(
 id INTEGER PRIMARY KEY, card_id INTEGER NOT NULL REFERENCES tech_cards, position INTEGER NOT NULL CHECK(position>0),
 kind TEXT NOT NULL, name TEXT NOT NULL, instructions TEXT NOT NULL, required INTEGER NOT NULL CHECK(required IN (0,1)),
 equipment_id INTEGER REFERENCES equipment, UNIQUE(card_id,position)
);
CREATE TABLE IF NOT EXISTS step_parameters(
 id INTEGER PRIMARY KEY, step_id INTEGER NOT NULL REFERENCES card_steps, name TEXT NOT NULL, unit TEXT NOT NULL,
 target REAL NOT NULL, minimum REAL NOT NULL, maximum REAL NOT NULL, required INTEGER NOT NULL CHECK(required IN (0,1)),
 CHECK(minimum<=target AND target<=maximum), UNIQUE(step_id,name)
);
CREATE TRIGGER IF NOT EXISTS card_approve_insert BEFORE INSERT ON tech_cards WHEN NEW.status='active'
 BEGIN SELECT RAISE(ABORT,'card_create_draft'); END;
CREATE TRIGGER IF NOT EXISTS card_approve_update BEFORE UPDATE ON tech_cards WHEN NEW.status='active'
 AND NOT EXISTS(SELECT 1 FROM card_steps WHERE card_id=NEW.id AND required=1)
 BEGIN SELECT RAISE(ABORT,'card_required_step'); END;
CREATE TRIGGER IF NOT EXISTS card_locked BEFORE UPDATE ON tech_cards
 WHEN (OLD.status='active' AND NEW.status NOT IN ('active','archived'))
 OR (OLD.status='archived' AND NEW.status<>'archived')
 OR (OLD.status IN ('active','archived') AND
     (NEW.product_id<>OLD.product_id OR NEW.version<>OLD.version OR NEW.name<>OLD.name))
 BEGIN SELECT RAISE(ABORT,'card_locked'); END;
CREATE TRIGGER IF NOT EXISTS card_step_insert BEFORE INSERT ON card_steps WHEN EXISTS(
 SELECT 1 FROM tech_cards WHERE id=NEW.card_id AND status IN ('active','archived'))
 BEGIN SELECT RAISE(ABORT,'card_locked'); END;
CREATE TRIGGER IF NOT EXISTS card_step_update BEFORE UPDATE ON card_steps WHEN EXISTS(
 SELECT 1 FROM tech_cards WHERE id IN (OLD.card_id,NEW.card_id) AND status IN ('active','archived'))
 BEGIN SELECT RAISE(ABORT,'card_locked'); END;
CREATE TRIGGER IF NOT EXISTS card_step_delete BEFORE DELETE ON card_steps WHEN EXISTS(
 SELECT 1 FROM tech_cards WHERE id=OLD.card_id AND status IN ('active','archived'))
 BEGIN SELECT RAISE(ABORT,'card_locked'); END;
CREATE TRIGGER IF NOT EXISTS card_param_insert BEFORE INSERT ON step_parameters WHEN EXISTS(
 SELECT 1 FROM card_steps s JOIN tech_cards c ON c.id=s.card_id WHERE s.id=NEW.step_id AND c.status IN ('active','archived'))
 BEGIN SELECT RAISE(ABORT,'card_locked'); END;
CREATE TRIGGER IF NOT EXISTS card_param_update BEFORE UPDATE ON step_parameters WHEN EXISTS(
 SELECT 1 FROM card_steps s JOIN tech_cards c ON c.id=s.card_id WHERE s.id IN (OLD.step_id,NEW.step_id) AND c.status IN ('active','archived'))
 BEGIN SELECT RAISE(ABORT,'card_locked'); END;
CREATE TRIGGER IF NOT EXISTS card_param_delete BEFORE DELETE ON step_parameters WHEN EXISTS(
 SELECT 1 FROM card_steps s JOIN tech_cards c ON c.id=s.card_id WHERE s.id=OLD.step_id AND c.status IN ('active','archived'))
 BEGIN SELECT RAISE(ABORT,'card_locked'); END;
CREATE TABLE IF NOT EXISTS orders(
 id INTEGER PRIMARY KEY, code TEXT NOT NULL UNIQUE, product_id INTEGER NOT NULL REFERENCES products,
 quantity INTEGER NOT NULL CHECK(quantity>0), due TEXT NOT NULL, author_id INTEGER NOT NULL REFERENCES users,
 status TEXT NOT NULL DEFAULT 'planned' CHECK(status IN ('planned','in_progress','completed','cancelled'))
);
CREATE TABLE IF NOT EXISTS batches(
 id INTEGER PRIMARY KEY, code TEXT NOT NULL UNIQUE, order_id INTEGER NOT NULL REFERENCES orders,
 mass_recipe_id INTEGER NOT NULL REFERENCES recipes, glaze_recipe_id INTEGER NOT NULL REFERENCES recipes,
 card_id INTEGER NOT NULL REFERENCES tech_cards, line TEXT NOT NULL, quantity INTEGER NOT NULL CHECK(quantity>0),
 status TEXT NOT NULL DEFAULT 'planned' CHECK(status IN ('planned','in_progress','quality','completed','blocked')),
 created TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, started TEXT, finished TEXT
);
CREATE TRIGGER IF NOT EXISTS batch_norms BEFORE INSERT ON batches WHEN NOT EXISTS(
 SELECT 1 FROM orders o JOIN recipes m ON m.id=NEW.mass_recipe_id JOIN recipes g ON g.id=NEW.glaze_recipe_id
 JOIN tech_cards t ON t.id=NEW.card_id WHERE o.id=NEW.order_id AND m.kind='mass' AND g.kind='glaze'
 AND m.product_id=o.product_id AND g.product_id=o.product_id AND t.product_id=o.product_id
 AND m.status='active' AND g.status='active' AND t.status='active')
 BEGIN SELECT RAISE(ABORT,'batch_norms'); END;
CREATE TRIGGER IF NOT EXISTS batch_norms_locked BEFORE UPDATE ON batches
 WHEN NEW.order_id<>OLD.order_id OR NEW.mass_recipe_id<>OLD.mass_recipe_id OR NEW.glaze_recipe_id<>OLD.glaze_recipe_id
 OR NEW.card_id<>OLD.card_id
 BEGIN SELECT RAISE(ABORT,'batch_norms'); END;
CREATE TRIGGER IF NOT EXISTS order_product_locked BEFORE UPDATE OF product_id ON orders
 WHEN NEW.product_id<>OLD.product_id AND EXISTS(SELECT 1 FROM batches WHERE order_id=OLD.id)
 BEGIN SELECT RAISE(ABORT,'batch_norms'); END;
CREATE TABLE IF NOT EXISTS batch_programs(
 batch_id INTEGER NOT NULL REFERENCES batches, program_id INTEGER NOT NULL REFERENCES equipment_programs,
 PRIMARY KEY(batch_id, program_id)
);
CREATE TABLE IF NOT EXISTS batch_raw(
 batch_id INTEGER NOT NULL REFERENCES batches, raw_lot_id INTEGER NOT NULL REFERENCES raw_lots,
 quantity REAL NOT NULL CHECK(quantity>0), PRIMARY KEY(batch_id,raw_lot_id)
);
CREATE TRIGGER IF NOT EXISTS raw_use_insert BEFORE INSERT ON batch_raw WHEN
 EXISTS(SELECT 1 FROM raw_lots WHERE id=NEW.raw_lot_id AND status='blocked')
 BEGIN SELECT RAISE(ABORT,'raw_blocked'); END;
CREATE TRIGGER IF NOT EXISTS raw_use_update BEFORE UPDATE ON batch_raw WHEN
 EXISTS(SELECT 1 FROM raw_lots WHERE id=NEW.raw_lot_id AND status='blocked')
 BEGIN SELECT RAISE(ABORT,'raw_blocked'); END;
CREATE TABLE IF NOT EXISTS executions(
 id INTEGER PRIMARY KEY, batch_id INTEGER NOT NULL REFERENCES batches, step_id INTEGER NOT NULL REFERENCES card_steps,
 status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','ready','running','done','skipped')),
 started TEXT, finished TEXT, started_by INTEGER REFERENCES users, finished_by INTEGER REFERENCES users,
 comment TEXT NOT NULL DEFAULT '', UNIQUE(batch_id,step_id)
);
CREATE UNIQUE INDEX IF NOT EXISTS one_current_step ON executions(batch_id) WHERE status IN ('ready','running');
CREATE TABLE IF NOT EXISTS step_values(
 execution_id INTEGER NOT NULL REFERENCES executions, parameter_id INTEGER NOT NULL REFERENCES step_parameters,
 value REAL NOT NULL, PRIMARY KEY(execution_id,parameter_id)
);
CREATE TRIGGER IF NOT EXISTS batch_closed_insert BEFORE INSERT ON batches WHEN NEW.status='completed' AND
 EXISTS(SELECT 1 FROM card_steps WHERE card_id=NEW.card_id AND required=1)
 BEGIN SELECT RAISE(ABORT,'steps_pending'); END;
CREATE TRIGGER IF NOT EXISTS batch_closed_update BEFORE UPDATE ON batches WHEN NEW.status='completed' AND EXISTS(
 SELECT 1 FROM card_steps s WHERE s.card_id=NEW.card_id AND s.required=1 AND
 NOT EXISTS(SELECT 1 FROM executions e WHERE e.batch_id=NEW.id AND e.step_id=s.id AND e.status='done'))
 BEGIN SELECT RAISE(ABORT,'steps_pending'); END;
CREATE TRIGGER IF NOT EXISTS closed_step_update BEFORE UPDATE ON executions WHEN OLD.status='done' AND
 EXISTS(SELECT 1 FROM batches WHERE id=OLD.batch_id AND status='completed') AND
 (NEW.status<>'done' OR NEW.batch_id<>OLD.batch_id OR NEW.step_id<>OLD.step_id)
 BEGIN SELECT RAISE(ABORT,'steps_pending'); END;
CREATE TRIGGER IF NOT EXISTS closed_step_delete BEFORE DELETE ON executions WHEN OLD.status='done' AND
 EXISTS(SELECT 1 FROM batches WHERE id=OLD.batch_id AND status='completed')
 BEGIN SELECT RAISE(ABORT,'steps_pending'); END;
CREATE TABLE IF NOT EXISTS telemetry(
 id INTEGER PRIMARY KEY, equipment_id INTEGER NOT NULL REFERENCES equipment, batch_id INTEGER REFERENCES batches,
 zone TEXT NOT NULL, temperature REAL NOT NULL, recorded TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS lab_specs(
 id INTEGER PRIMARY KEY, kind TEXT NOT NULL CHECK(kind IN ('raw','mass','glaze','finished')),
 name TEXT NOT NULL, unit TEXT NOT NULL, minimum REAL NOT NULL, maximum REAL NOT NULL,
 required INTEGER NOT NULL DEFAULT 1 CHECK(required IN (0,1)), CHECK(minimum<=maximum), UNIQUE(kind,name)
);
CREATE TABLE IF NOT EXISTS lab_tests(
 id INTEGER PRIMARY KEY, raw_lot_id INTEGER REFERENCES raw_lots, batch_id INTEGER REFERENCES batches,
 kind TEXT NOT NULL CHECK(kind IN ('raw','mass','glaze','finished')), type TEXT NOT NULL,
 analyst_id INTEGER NOT NULL REFERENCES users, appointed TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 created TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, priority TEXT NOT NULL, comment TEXT NOT NULL DEFAULT '',
 status TEXT NOT NULL DEFAULT 'open' CHECK(status IN ('open','done')), result TEXT CHECK(result IN ('pass','fail')),
 finished TEXT, CHECK((kind='raw' AND raw_lot_id IS NOT NULL AND batch_id IS NULL) OR
 (kind<>'raw' AND batch_id IS NOT NULL AND raw_lot_id IS NULL))
);
CREATE UNIQUE INDEX IF NOT EXISTS one_raw_test ON lab_tests(raw_lot_id) WHERE status='open';
CREATE UNIQUE INDEX IF NOT EXISTS one_batch_test ON lab_tests(batch_id,kind) WHERE status='open';
CREATE TABLE IF NOT EXISTS lab_results(
 test_id INTEGER NOT NULL REFERENCES lab_tests, spec_id INTEGER NOT NULL REFERENCES lab_specs,
 value REAL, PRIMARY KEY(test_id,spec_id)
);
CREATE TABLE IF NOT EXISTS lab_decisions(
 id INTEGER PRIMARY KEY, test_id INTEGER NOT NULL UNIQUE REFERENCES lab_tests, author_id INTEGER NOT NULL REFERENCES users,
 decision TEXT NOT NULL CHECK(decision IN ('released','blocked')), comment TEXT NOT NULL DEFAULT '',
 created TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, CHECK(decision<>'blocked' OR length(trim(comment))>0)
);
CREATE TABLE IF NOT EXISTS incidents(
 id INTEGER PRIMARY KEY, batch_id INTEGER NOT NULL REFERENCES batches, execution_id INTEGER REFERENCES executions,
 author_id INTEGER NOT NULL REFERENCES users, severity TEXT NOT NULL CHECK(severity IN ('warning','critical')),
 description TEXT NOT NULL, state TEXT NOT NULL DEFAULT 'open' CHECK(state IN ('open','resolved')),
 resolved_by INTEGER REFERENCES users, resolution TEXT, created TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS deviations(
 id INTEGER PRIMARY KEY, execution_id INTEGER NOT NULL REFERENCES executions, parameter_id INTEGER NOT NULL REFERENCES step_parameters,
 value REAL NOT NULL, comment TEXT NOT NULL, created TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS events(
 id INTEGER PRIMARY KEY, batch_id INTEGER REFERENCES batches, user_id INTEGER REFERENCES users, action TEXT NOT NULL,
 entity TEXT NOT NULL, entity_id INTEGER NOT NULL, detail TEXT NOT NULL DEFAULT '', created TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS notifications(
 id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users, event_id INTEGER NOT NULL REFERENCES events,
 read_at TEXT, UNIQUE(user_id,event_id)
);

CREATE TABLE IF NOT EXISTS inspection_routes(
 id INTEGER PRIMARY KEY, line TEXT NOT NULL UNIQUE, name TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS inspection_points(
 id INTEGER PRIMARY KEY, route_id INTEGER NOT NULL REFERENCES inspection_routes, equipment_id INTEGER NOT NULL REFERENCES equipment,
 position INTEGER NOT NULL CHECK(position>0), location TEXT NOT NULL, instruction TEXT NOT NULL,
 UNIQUE(route_id,position), UNIQUE(route_id,equipment_id)
);
CREATE TABLE IF NOT EXISTS inspection_parameters(
 id INTEGER PRIMARY KEY, point_id INTEGER NOT NULL REFERENCES inspection_points, name TEXT NOT NULL, unit TEXT NOT NULL,
 minimum REAL NOT NULL, maximum REAL NOT NULL CHECK(minimum<=maximum), UNIQUE(point_id,name)
);
CREATE TABLE IF NOT EXISTS inspections(
 id INTEGER PRIMARY KEY, route_id INTEGER NOT NULL REFERENCES inspection_routes, user_id INTEGER NOT NULL REFERENCES users,
 status TEXT NOT NULL DEFAULT 'open' CHECK(status IN ('open','done')),
 started TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, finished TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS current_inspection ON inspections(route_id,user_id) WHERE status='open';
CREATE TABLE IF NOT EXISTS inspection_checks(
 inspection_id INTEGER NOT NULL REFERENCES inspections, point_id INTEGER NOT NULL REFERENCES inspection_points,
 checked TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, severity TEXT CHECK(severity IN ('warning','critical')),
 note TEXT NOT NULL DEFAULT '', PRIMARY KEY(inspection_id,point_id), CHECK(severity IS NULL OR length(trim(note))>0)
);
CREATE TABLE IF NOT EXISTS inspection_readings(
 inspection_id INTEGER NOT NULL, point_id INTEGER NOT NULL, parameter_id INTEGER NOT NULL REFERENCES inspection_parameters,
 value REAL NOT NULL, PRIMARY KEY(inspection_id,parameter_id),
 FOREIGN KEY(inspection_id,point_id) REFERENCES inspection_checks
);
