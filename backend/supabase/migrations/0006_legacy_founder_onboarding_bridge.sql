-- Compatibility bridge for projects that applied the retired 0001-0005 chain.
-- Fresh projects use 0001_baseline.sql, which already provides this RPC.

do $bridge$
begin
  if to_regprocedure('public.create_founder_community(jsonb)') is null then
    execute $sql$
      create function public.create_founder_community(p_payload jsonb)
      returns jsonb
      language plpgsql
      security definer
      set search_path=public
      as $founder$
      declare
        community uuid;
        building uuid;
        selected_building uuid;
        unit uuid;
        member uuid;
        existing_community uuid;
        item jsonb;
        founder_profile uuid := (p_payload->>'founder_profile_id')::uuid;
        founder_structure text := p_payload->'admin_profile'->>'founderStructureId';
        unit_code text := btrim(p_payload->'admin_profile'->>'unitNumber');
        type_value text := p_payload->>'community_type';
      begin
        perform pg_advisory_xact_lock(hashtext(founder_profile::text));
        select m.community_id, m.id into existing_community, member
          from public.community_memberships m
         where m.profile_id=founder_profile and m.status='active' and m.ended_at is null
         order by m.is_default_community desc limit 1;
        if existing_community is not null then
          select u.id into unit from public.units u
            join public.unit_residencies r on r.unit_id=u.id
           where r.membership_id=member and r.ended_at is null limit 1;
          return jsonb_build_object(
            'community', jsonb_build_object(
              'id', existing_community,
              'name', (select name from public.communities where id=existing_community),
              'communityType', (select community_type from public.communities where id=existing_community),
              'enabledModules', coalesce((select jsonb_agg(feature_code order by feature_code) from public.community_features where community_id=existing_community and is_enabled), '[]'::jsonb),
              'unitType', case when (select community_type from public.communities where id=existing_community)='apartment' then 'Blocks' else 'Villas' end,
              'unitCount', (select count(*) from public.units where community_id=existing_community)
            ),
            'admin', jsonb_build_object(
              'id', founder_profile,
              'fullName', (select full_name from public.profiles where id=founder_profile),
              'role', 'Admin',
              'unitNumber', (select unit_code from public.units where id=unit),
              'phone', (select phone_e164 from public.profiles where id=founder_profile)
            )
          );
        end if;
        if type_value not in ('apartment','layout_villa') or unit_code = '' then
          raise exception 'Invalid founder community payload';
        end if;

        insert into public.profiles(id,full_name,display_email,phone_e164)
        values(founder_profile,p_payload->'admin_profile'->>'fullName',(p_payload->>'founder_email')::citext,nullif(p_payload->'admin_profile'->>'phone',''))
        on conflict(id) do update set full_name=excluded.full_name,display_email=excluded.display_email,phone_e164=coalesce(excluded.phone_e164,public.profiles.phone_e164),updated_at=now();
        insert into public.communities(name,community_type,address_line1,city,state,postal_code)
        values(p_payload->>'name',type_value,p_payload->>'address_line1',p_payload->>'city',p_payload->>'state',p_payload->>'postal_code') returning id into community;

        if type_value='apartment' then
          for item in select * from jsonb_array_elements(p_payload->'blocks') loop
            insert into public.buildings(community_id,name,code,building_type,map_x,map_y)
            values(community,item->>'name',item->>'id','block',(p_payload->'block_locations'->(item->>'id')->>'x')::numeric,(p_payload->'block_locations'->(item->>'id')->>'y')::numeric)
            returning id into building;
            if founder_structure is null or founder_structure=item->>'id' then selected_building := building; end if;
          end loop;
          if selected_building is null then raise exception 'Founder block is invalid'; end if;
          insert into public.units(community_id,building_id,unit_code,unit_type)
          values(community,selected_building,unit_code,'flat') returning id into unit;
        else
          for item in select * from jsonb_array_elements(p_payload->'villas') loop
            insert into public.buildings(community_id,name,code,building_type,map_x,map_y)
            values(community,item->>'name',item->>'id','villa',(p_payload->'villa_locations'->(item->>'id')->>'x')::numeric,(p_payload->'villa_locations'->(item->>'id')->>'y')::numeric)
            returning id into building;
            insert into public.units(community_id,building_id,unit_code,unit_type,map_x,map_y)
            values(community,building,case when founder_structure=item->>'id' then unit_code else item->>'name' end,'villa',(p_payload->'villa_locations'->(item->>'id')->>'x')::numeric,(p_payload->'villa_locations'->(item->>'id')->>'y')::numeric);
            if founder_structure is null or founder_structure=item->>'id' then selected_building := building; end if;
          end loop;
          select u.id into unit from public.units u where u.community_id=community and u.building_id=selected_building limit 1;
          if unit is null then raise exception 'Founder villa is invalid'; end if;
        end if;

        insert into public.community_memberships(community_id,profile_id,role,status,is_default_community)
        values(community,founder_profile,'admin','active',true) returning id into member;
        insert into public.unit_residencies(unit_id,membership_id,relationship_type,is_primary_contact)
        values(unit,member,'owner',true);
        insert into public.community_admin_terms(community_id,admin_membership_id) values(community,member);
        insert into public.community_features(community_id,feature_code,is_enabled)
        select community,value,true from jsonb_array_elements_text(coalesce(p_payload->'enabled_features','[]'::jsonb)) value
          join public.feature_catalog f on f.code=value and f.is_active on conflict do nothing;
        insert into public.audit_events(community_id,actor_membership_id,action,entity_type,entity_id,after_data)
        values(community,member,'community.created','community',community,jsonb_build_object('founder_profile_id',founder_profile,'community_type',type_value));
        return jsonb_build_object(
          'community', jsonb_build_object('id',community,'name',p_payload->>'name','communityType',type_value,'enabledModules',coalesce(p_payload->'enabled_features','[]'::jsonb),'unitType',case when type_value='apartment' then 'Blocks' else 'Villas' end,'unitCount',case when type_value='apartment' then jsonb_array_length(p_payload->'blocks') else jsonb_array_length(p_payload->'villas') end),
          'admin', jsonb_build_object('id',founder_profile,'fullName',p_payload->'admin_profile'->>'fullName','role','Admin','unitNumber',unit_code,'phone',p_payload->'admin_profile'->>'phone')
        );
      end;
      $founder$;
    $sql$;
  end if;
end
$bridge$;

revoke all on function public.create_founder_community(jsonb) from public, anon, authenticated;
grant execute on function public.create_founder_community(jsonb) to service_role;
