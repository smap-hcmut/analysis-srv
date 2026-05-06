from internal.domain.loader import DomainLoader


def test_real_logistics_domains_load_shared_ontology():
    registry = DomainLoader.load_from_dir("config/domains", fallback_code="_default")

    ahamove = registry.lookup("ahamove")
    grab = registry.lookup("grab")

    assert ahamove.ontology_path == "config/ontology/logistics_vn.yaml"
    assert grab.ontology_path == "config/ontology/logistics_vn.yaml"

    ahamove_ontology = ahamove.load_ontology_registry().ontology
    grab_ontology = grab.load_ontology_registry().ontology

    assert ahamove_ontology.domain_id == "logistics_vn"
    assert grab_ontology.domain_id == "logistics_vn"
    assert len(ahamove_ontology.entities) >= 6
    assert len(grab_ontology.topics) >= 6
