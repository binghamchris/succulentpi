SELECT
  plant.pot.soil.moisture_top_a0 AS plant_pot_soil_moisture_top,
  plant.pot.soil.moisture_middle_a1 AS plant_pot_soil_moisture_middle,
  plant.pot.soil.moisture_bottom_a2 AS plant_pot_soil_moisture_bottom,
  plant.env.visible_light AS plant_env_visiblelight,
  plant.env.uv_light AS plant_env_uvlight,
  plant.env.ir_light AS plant_env_irlight,
  plant.images.infrared AS plant_image_infrared,
  room.env.dew_point AS room_env_dewpoint,
  room.env.temp AS room_env_temperature,
  room.env.rel_humid AS room_env_relativehumidity,
  room.env.abs_humid AS room_env_absolutehumidty,
  room.env.co2 AS room_env_co2,
  room.env.voc_total AS room_env_voctotal,
  room.env.voc_h2 AS room_env_voch2,
  room.env.voc_ethanol AS room_env_vocethanol,
  room.env.pm25 AS room_env_pm25
FROM
  'succulentpi/readings'